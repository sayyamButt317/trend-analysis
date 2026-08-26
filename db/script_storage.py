import asyncio
import logging
from typing import Any

from agents.scriptgenerator.schemas.script_request import ScriptGenerationRequest
from config.credential_config import config, resolve_supabase_api_key
from db.connection import get_supabase

logger = logging.getLogger(__name__)

AGENT_TYPE = "script_generation"


def _is_storage_configured() -> bool:
    return bool((config.SUPABASE_URL or "").strip() and resolve_supabase_api_key())


def _prompts_table() -> str:
    return (config.SUPABASE_TABLE_PROMPTS or "prompts").strip()


def _script_table() -> str:
    return (config.SUPABASE_TABLE_SCRIPT or "script").strip()


def _request_summary(request: ScriptGenerationRequest) -> str:
    suggestion = dict(request.content_suggestion or {})
    return (
        str(suggestion.get("title") or suggestion.get("topic") or "").strip()
        or (request.user_request or "").strip()[:200]
        or "Script generation"
    )


def _result_summary(result: dict[str, Any]) -> str | None:
    script = result.get("script") or {}
    project = result.get("project") or {}
    if isinstance(script, dict):
        title = script.get("title") or script.get("headline")
        if title:
            return str(title).strip()[:500]
    if isinstance(project, dict):
        name = project.get("name") or project.get("title")
        if name:
            return str(name).strip()[:500]
    content_type = result.get("content_type") or "script"
    scenes = result.get("scenes") or []
    count = len(scenes) if isinstance(scenes, list) else 0
    return f"{content_type} script — {count} scene(s)" if count else None


def _platform_from_request(request: ScriptGenerationRequest) -> str | None:
    suggestion = dict(request.content_suggestion or {})
    platform = suggestion.get("platform")
    if platform:
        return str(platform).strip().lower() or None
    return None


def _insert_prompt_sync(request: ScriptGenerationRequest) -> str:
    client = get_supabase()
    suggestion = dict(request.content_suggestion or {})
    company_id = request.company_id or suggestion.get("company_id")
    row = {
        "agent_type": AGENT_TYPE,
        "company_data": _request_summary(request),
        "region": suggestion.get("region") or "unspecified",
        "company_name": suggestion.get("company_name") or suggestion.get("title"),
        "company_id": company_id,
        "competitors": [],
        "request_payload": request.model_dump(mode="json"),
    }
    response = client.table(_prompts_table()).insert(row).execute()
    data = response.data or []
    if not data:
        raise RuntimeError("Supabase returned no prompt row after insert")
    return str(data[0]["id"])


def _insert_script_sync(
    *,
    prompt_id: str,
    request: ScriptGenerationRequest,
    result: dict[str, Any],
    duration_sec: float,
    company_id: str | None = None,
) -> str:
    client = get_supabase()
    meta = result.get("meta") or {}
    suggestion = dict(request.content_suggestion or {})
    scenes = result.get("scenes") or []
    characters = result.get("characters") or []
    row = {
        "prompt_id": prompt_id,
        "agent_type": AGENT_TYPE,
        "company_id": company_id or meta.get("company_id") or result.get("company_id"),
        "status": meta.get("status") or ("success" if result.get("success") else "failed"),
        "success": bool(result.get("success")),
        "error": result.get("error"),
        "summary": _result_summary(result),
        "content_type": result.get("content_type") or request.content_type,
        "aspect_ratio": meta.get("aspect_ratio") or request.aspect_ratio,
        "style": meta.get("style") or request.style,
        "duration_seconds": meta.get("duration_seconds") or request.duration_seconds,
        "platform": _platform_from_request(request),
        "scenes_count": len(scenes) if isinstance(scenes, list) else 0,
        "characters_count": len(characters) if isinstance(characters, list) else 0,
        "duration_sec": round(duration_sec, 3),
        "request_payload": request.model_dump(mode="json"),
        "result": result,
        "project": result.get("project") or {},
        "script": result.get("script") or {},
        "characters": characters if isinstance(characters, list) else [],
        "scenes": scenes if isinstance(scenes, list) else [],
        "content_suggestion": suggestion,
    }
    response = client.table(_script_table()).insert(row).execute()
    data = response.data or []
    if not data:
        raise RuntimeError(
            f"Supabase returned no row after insert into {_script_table()}. "
            "Create the table with db/migrations/008_script.sql"
        )
    return str(data[0]["id"])


async def save_script_generation_run(
    request: ScriptGenerationRequest,
    result: dict[str, Any],
    *,
    duration_sec: float,
) -> dict[str, str | None]:
    """Persist script generation output into prompts + script tables."""
    if not _is_storage_configured():
        message = (
            "Supabase storage skipped: use SUPABASE_SERVICE_ROLE_KEY (JWT) from "
            "Supabase Dashboard → API. sb_publishable_ keys are not supported."
        )
        if (config.SUPABASE_KEY or "").startswith("sb_publishable_"):
            logger.warning(message)
            return {"prompt_id": None, "script_id": None, "storage_error": message}
        logger.warning("Supabase not configured; skipping script generation persistence")
        return {"prompt_id": None, "script_id": None, "storage_error": "Supabase not configured"}

    try:
        prompt_id = await asyncio.to_thread(_insert_prompt_sync, request)
        suggestion = dict(request.content_suggestion or {})
        company_id = request.company_id or suggestion.get("company_id")
        script_id = await asyncio.to_thread(
            _insert_script_sync,
            prompt_id=prompt_id,
            request=request,
            result=result,
            duration_sec=duration_sec,
            company_id=company_id,
        )
        logger.info(
            "Saved script generation prompt_id=%s script_id=%s company_id=%s table=%s",
            prompt_id,
            script_id,
            company_id,
            _script_table(),
        )
        return {"prompt_id": prompt_id, "script_id": script_id, "storage_error": None}
    except Exception as exc:
        logger.exception("Failed to save script generation to Supabase")
        message = str(exc)
        table = _script_table()
        if table.lower() in message.lower() or "PGRST205" in message or "does not exist" in message.lower():
            message = (
                f"{message} — Create the table in Supabase SQL Editor using "
                "db/migrations/008_script.sql "
                f"(table name from SUPABASE_TABLE_SCRIPT={table})"
            )
        return {"prompt_id": None, "script_id": None, "storage_error": message}


def _fetch_by_company_id_sync(company_id: str) -> dict[str, Any] | None:
    client = get_supabase()
    response = (
        client.table(_script_table())
        .select(
            "id,prompt_id,company_id,created_at,success,status,summary,content_type,"
            "aspect_ratio,style,duration_seconds,platform,scenes_count,characters_count,"
            "duration_sec,project,script,characters,scenes,content_suggestion,result,agent_type"
        )
        .eq("company_id", company_id)
        .eq("agent_type", AGENT_TYPE)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


async def get_script_generation(company_id: str) -> dict[str, Any] | None:
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
        client.table(_script_table())
        .select(
            "id,prompt_id,company_id,created_at,success,status,summary,content_type,"
            "platform,scenes_count,characters_count,duration_sec,agent_type"
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


async def list_script_generations(
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


def _resolve_script_id_sync(*, company_id: str | None = None, script_id: str | None = None) -> str:
    client = get_supabase()
    if script_id:
        response = (
            client.table(_script_table())
            .select("id")
            .eq("id", script_id.strip())
            .eq("agent_type", AGENT_TYPE)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise LookupError(f"Script not found: {script_id}")
        return str(rows[0]["id"])

    company_id = (company_id or "").strip()
    if not company_id:
        raise ValueError("company_id or script_id is required")

    response = (
        client.table(_script_table())
        .select("id")
        .eq("company_id", company_id)
        .eq("agent_type", AGENT_TYPE)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise LookupError(f"Script generation not found for company_id: {company_id}")
    return str(rows[0]["id"])


def _delete_script_sync(script_id: str) -> dict[str, Any]:
    client = get_supabase()
    script_table = _script_table()
    prompts_table = _prompts_table()

    existing = (
        client.table(script_table)
        .select("id,prompt_id,company_id,agent_type")
        .eq("id", script_id)
        .eq("agent_type", AGENT_TYPE)
        .limit(1)
        .execute()
    )
    rows = existing.data or []
    if not rows:
        raise LookupError(f"Script not found: {script_id}")

    row = rows[0]
    prompt_id = row.get("prompt_id")
    company_id = row.get("company_id")

    script_resp = (
        client.table(script_table)
        .delete()
        .eq("id", script_id)
        .eq("agent_type", AGENT_TYPE)
        .execute()
    )
    if not (script_resp.data or []):
        check = (
            client.table(script_table)
            .select("id")
            .eq("id", script_id)
            .limit(1)
            .execute()
        )
        if check.data:
            raise RuntimeError(f"Failed to delete script row: {script_id}")

    deleted_prompt = False
    if prompt_id:
        remaining = (
            client.table(script_table)
            .select("id")
            .eq("prompt_id", prompt_id)
            .limit(1)
            .execute()
        )
        if not (remaining.data or []):
            try:
                client.table(prompts_table).delete().eq("id", prompt_id).execute()
                deleted_prompt = True
            except Exception:
                logger.warning(
                    "Failed deleting orphaned prompt_id=%s",
                    prompt_id,
                    exc_info=True,
                )

    return {
        "script_id": script_id,
        "prompt_id": prompt_id,
        "company_id": company_id,
        "deleted_prompt": deleted_prompt,
    }


async def delete_script_generation(
    *,
    company_id: str | None = None,
    script_id: str | None = None,
) -> dict[str, Any]:
    if not _is_storage_configured():
        raise RuntimeError("Supabase is not configured")

    resolved_id = await asyncio.to_thread(
        _resolve_script_id_sync,
        company_id=company_id,
        script_id=script_id,
    )
    result = await asyncio.to_thread(_delete_script_sync, resolved_id)
    logger.info(
        "Deleted script generation script_id=%s company_id=%s prompt_id=%s prompt_deleted=%s",
        result.get("script_id"),
        result.get("company_id"),
        result.get("prompt_id"),
        result.get("deleted_prompt"),
    )
    return {"success": True, **result}
