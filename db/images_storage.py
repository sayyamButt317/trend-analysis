import asyncio
import copy
import logging
from typing import Any

from agents.imagegeneration.schemas.image_request import ImageGenerationRequest
from config.credential_config import config, resolve_supabase_api_key
from db.connection import get_supabase

logger = logging.getLogger(__name__)

AGENT_TYPE = "image_generation"


def _is_storage_configured() -> bool:
    return bool((config.SUPABASE_URL or "").strip() and resolve_supabase_api_key())


def _prompts_table() -> str:
    return (config.SUPABASE_TABLE_PROMPTS or "prompts").strip()


def _images_table() -> str:
    return (config.SUPABASE_TABLE_IMAGES or "images").strip()


def _strip_image_payloads(value: Any) -> Any:
    """Remove large base64 blobs before persisting to Postgres."""
    if isinstance(value, list):
        return [_strip_image_payloads(item) for item in value]
    if isinstance(value, dict):
        cleaned = {key: _strip_image_payloads(item) for key, item in value.items()}
        cleaned.pop("image_base64", None)
        cleaned.pop("data_url", None)
        return cleaned
    return value


def _request_summary(request: ImageGenerationRequest) -> str:
    project = dict(request.project or {})
    script = dict(request.script or {})
    return (
        str(project.get("name") or project.get("title") or "").strip()
        or str(script.get("title") or script.get("headline") or "").strip()
        or f"{request.platform} {request.purpose} images"
    )


def _result_summary(result: dict[str, Any]) -> str | None:
    script = result.get("script") or {}
    project = result.get("project") or {}
    platform = result.get("platform") or "social"
    purpose = result.get("purpose") or "post"
    images = result.get("generated_images") or []
    count = len(images) if isinstance(images, list) else 0

    title = None
    if isinstance(script, dict):
        title = script.get("title") or script.get("headline")
    if not title and isinstance(project, dict):
        title = project.get("name") or project.get("title")
    if title and count:
        return f"{platform} {purpose} — {count} image(s) — {title}"[:500]
    if count:
        return f"{platform} {purpose} — {count} image(s)"
    return None


def _insert_prompt_sync(request: ImageGenerationRequest) -> str:
    client = get_supabase()
    project = dict(request.project or {})
    company_id = request.company_id or project.get("company_id") or project.get("id")
    row = {
        "agent_type": AGENT_TYPE,
        "company_data": _request_summary(request),
        "region": project.get("region") or "unspecified",
        "company_name": project.get("name") or project.get("title"),
        "company_id": company_id,
        "competitors": [],
        "request_payload": request.model_dump(mode="json"),
    }
    response = client.table(_prompts_table()).insert(row).execute()
    data = response.data or []
    if not data:
        raise RuntimeError("Supabase returned no prompt row after insert")
    return str(data[0]["id"])


def _insert_images_sync(
    *,
    prompt_id: str,
    request: ImageGenerationRequest,
    result: dict[str, Any],
    duration_sec: float,
    company_id: str | None = None,
) -> str:
    client = get_supabase()
    meta = result.get("meta") or {}
    stored_result = _strip_image_payloads(copy.deepcopy(result))
    jobs = stored_result.get("image_jobs") or []
    images = stored_result.get("generated_images") or []
    row = {
        "prompt_id": prompt_id,
        "agent_type": AGENT_TYPE,
        "company_id": company_id or meta.get("company_id") or result.get("company_id"),
        "status": meta.get("status") or ("success" if result.get("success") else "failed"),
        "success": bool(result.get("success")),
        "error": result.get("error"),
        "summary": _result_summary(result),
        "platform": result.get("platform") or request.platform,
        "purpose": result.get("purpose") or request.purpose,
        "aspect_ratio": result.get("aspect_ratio") or request.resolve_aspect_ratio(),
        "style": meta.get("style") or request.style,
        "images_count": len(images) if isinstance(images, list) else 0,
        "jobs_count": len(jobs) if isinstance(jobs, list) else 0,
        "duration_sec": round(duration_sec, 3),
        "request_payload": request.model_dump(mode="json"),
        "result": stored_result,
        "project": stored_result.get("project") or {},
        "script": stored_result.get("script") or {},
        "image_jobs": jobs if isinstance(jobs, list) else [],
        "generated_images": images if isinstance(images, list) else [],
    }
    response = client.table(_images_table()).insert(row).execute()
    data = response.data or []
    if not data:
        raise RuntimeError(
            f"Supabase returned no row after insert into {_images_table()}. "
            "Create the table with db/migrations/009_images.sql"
        )
    return str(data[0]["id"])


async def save_image_generation_run(
    request: ImageGenerationRequest,
    result: dict[str, Any],
    *,
    duration_sec: float,
) -> dict[str, str | None]:
    """Persist image generation output into prompts + images tables."""
    if not _is_storage_configured():
        message = (
            "Supabase storage skipped: use SUPABASE_SERVICE_ROLE_KEY (JWT) from "
            "Supabase Dashboard → API. sb_publishable_ keys are not supported."
        )
        if (config.SUPABASE_KEY or "").startswith("sb_publishable_"):
            logger.warning(message)
            return {"prompt_id": None, "images_id": None, "storage_error": message}
        logger.warning("Supabase not configured; skipping image generation persistence")
        return {"prompt_id": None, "images_id": None, "storage_error": "Supabase not configured"}

    try:
        prompt_id = await asyncio.to_thread(_insert_prompt_sync, request)
        project = dict(request.project or {})
        company_id = request.company_id or project.get("company_id") or project.get("id")
        images_id = await asyncio.to_thread(
            _insert_images_sync,
            prompt_id=prompt_id,
            request=request,
            result=result,
            duration_sec=duration_sec,
            company_id=company_id,
        )
        logger.info(
            "Saved image generation prompt_id=%s images_id=%s company_id=%s table=%s",
            prompt_id,
            images_id,
            company_id,
            _images_table(),
        )
        return {"prompt_id": prompt_id, "images_id": images_id, "storage_error": None}
    except Exception as exc:
        logger.exception("Failed to save image generation to Supabase")
        message = str(exc)
        table = _images_table()
        if table.lower() in message.lower() or "PGRST205" in message or "does not exist" in message.lower():
            message = (
                f"{message} — Create the table in Supabase SQL Editor using "
                "db/migrations/009_images.sql "
                f"(table name from SUPABASE_TABLE_IMAGES={table})"
            )
        return {"prompt_id": None, "images_id": None, "storage_error": message}


def _fetch_by_company_id_sync(company_id: str) -> dict[str, Any] | None:
    client = get_supabase()
    response = (
        client.table(_images_table())
        .select(
            "id,prompt_id,company_id,created_at,success,status,summary,platform,purpose,"
            "aspect_ratio,style,images_count,jobs_count,duration_sec,project,script,"
            "image_jobs,generated_images,result,agent_type"
        )
        .eq("company_id", company_id)
        .eq("agent_type", AGENT_TYPE)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


async def get_image_generation(company_id: str) -> dict[str, Any] | None:
    if not _is_storage_configured():
        raise RuntimeError("Supabase is not configured")
    company_id = (company_id or "").strip()
    if not company_id:
        raise ValueError("company_id is required")
    return await asyncio.to_thread(_fetch_by_company_id_sync, company_id)


def _list_runs_sync(
    *,
    limit: int = 20,
    company_id: str | None = None,
) -> list[dict[str, Any]]:
    client = get_supabase()
    query = (
        client.table(_images_table())
        .select(
            "id,prompt_id,company_id,created_at,success,status,summary,platform,purpose,"
            "aspect_ratio,images_count,jobs_count,duration_sec,agent_type"
        )
        .eq("agent_type", AGENT_TYPE)
    )
    if company_id:
        query = query.eq("company_id", company_id.strip())
    response = (
        query.order("created_at", desc=True)
        .limit(max(1, min(limit, 100)))
        .execute()
    )
    return response.data or []


async def list_image_generations(
    *,
    limit: int = 20,
    company_id: str | None = None,
) -> list[dict[str, Any]]:
    if not _is_storage_configured():
        raise RuntimeError("Supabase is not configured")
    return await asyncio.to_thread(
        _list_runs_sync,
        limit=limit,
        company_id=company_id,
    )
