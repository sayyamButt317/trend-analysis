import asyncio
import logging
from typing import Any

from agents.contentrecommendation.schemas.content_request import ContentRecommendationRequest
from config.credential_config import config, resolve_supabase_api_key
from db.connection import get_supabase

logger = logging.getLogger(__name__)

AGENT_TYPE = "content_recommendation"


def _is_storage_configured() -> bool:
    return bool((config.SUPABASE_URL or "").strip() and resolve_supabase_api_key())


def _prompts_table() -> str:
    return (config.SUPABASE_TABLE_PROMPTS or "prompts").strip()


def _content_recommendation_table() -> str:
    return (config.SUPABASE_TABLE_CONTENT_RECOMMENDATION or "content_recommendation").strip()


def _request_summary(request: ContentRecommendationRequest) -> str:
    company = dict(request.company or {})
    return (
        company.get("name")
        or company.get("description")
        or "Content recommendation"
    )


def _result_summary(result: dict[str, Any]) -> str | None:
    recommendation = result.get("recommendation") or {}
    if isinstance(recommendation, dict):
        headline = recommendation.get("headline") or recommendation.get("summary")
        if headline:
            return str(headline).strip()[:500] or None
    calendar = result.get("content_calendar") or {}
    items = calendar.get("items") or []
    if items:
        first = items[0] if isinstance(items[0], dict) else {}
        title = first.get("title") or first.get("topic")
        if title:
            return f"{len(items)} calendar items — {title}"[:500]
    ideas = result.get("content_ideas") or []
    if ideas:
        return f"{len(ideas)} content ideas"
    return None


def _insert_prompt_sync(request: ContentRecommendationRequest) -> str:
    client = get_supabase()
    company = dict(request.company or {})
    row = {
        "agent_type": AGENT_TYPE,
        "company_data": _request_summary(request),
        "region": company.get("region") or "unspecified",
        "company_name": company.get("name"),
        "company_id": request.company_id or company.get("company_id") or company.get("id"),
        "competitors": [],
        "request_payload": request.model_dump(mode="json"),
    }
    response = client.table(_prompts_table()).insert(row).execute()
    data = response.data or []
    if not data:
        raise RuntimeError("Supabase returned no prompt row after insert")
    return str(data[0]["id"])


def _insert_content_recommendation_sync(
    *,
    prompt_id: str,
    request: ContentRecommendationRequest,
    result: dict[str, Any],
    duration_sec: float,
    company_id: str | None = None,
) -> str:
    client = get_supabase()
    meta = result.get("meta") or {}
    company = dict(request.company or {})
    calendar = result.get("content_calendar") or {}
    calendar_items = calendar.get("items") or []
    ideas = result.get("content_ideas") or []
    platforms = meta.get("platforms") or request.platforms or []
    row = {
        "prompt_id": prompt_id,
        "agent_type": AGENT_TYPE,
        "company_id": company_id or meta.get("company_id") or result.get("company_id"),
        "company_name": company.get("name"),
        "status": meta.get("status") or ("success" if result.get("success") else "failed"),
        "success": bool(result.get("success")),
        "error": result.get("error"),
        "warning": result.get("warning"),
        "summary": _result_summary(result),
        "platforms": [str(p).strip().lower() for p in platforms if str(p).strip()],
        "calendar_days": meta.get("calendar_days") or request.calendar_days,
        "idea_count": meta.get("idea_count") or request.idea_count,
        "ideas_count": len(ideas) if isinstance(ideas, list) else 0,
        "calendar_items_count": len(calendar_items) if isinstance(calendar_items, list) else 0,
        "duration_sec": round(duration_sec, 3),
        "request_payload": request.model_dump(mode="json"),
        "result": result,
        "content_calendar": calendar,
        "content_ideas": ideas if isinstance(ideas, list) else [],
        "recommendation": result.get("recommendation") or {},
    }
    response = client.table(_content_recommendation_table()).insert(row).execute()
    data = response.data or []
    if not data:
        raise RuntimeError(
            f"Supabase returned no row after insert into {_content_recommendation_table()}. "
            "Create the table with db/migrations/007_content_recommendation.sql"
        )
    return str(data[0]["id"])


async def save_content_recommendation_run(
    request: ContentRecommendationRequest,
    result: dict[str, Any],
    *,
    duration_sec: float,
) -> dict[str, str | None]:
    """Persist content recommendation output into prompts + content_recommendation tables."""
    if not _is_storage_configured():
        message = (
            "Supabase storage skipped: use SUPABASE_SERVICE_ROLE_KEY (JWT) from "
            "Supabase Dashboard → API. sb_publishable_ keys are not supported."
        )
        if (config.SUPABASE_KEY or "").startswith("sb_publishable_"):
            logger.warning(message)
            return {
                "prompt_id": None,
                "content_recommendation_id": None,
                "storage_error": message,
            }
        logger.warning("Supabase not configured; skipping content recommendation persistence")
        return {
            "prompt_id": None,
            "content_recommendation_id": None,
            "storage_error": "Supabase not configured",
        }

    try:
        prompt_id = await asyncio.to_thread(_insert_prompt_sync, request)
        company_id = (
            request.company_id
            or (request.company or {}).get("company_id")
            or (request.company or {}).get("id")
        )
        content_recommendation_id = await asyncio.to_thread(
            _insert_content_recommendation_sync,
            prompt_id=prompt_id,
            request=request,
            result=result,
            duration_sec=duration_sec,
            company_id=company_id,
        )
        logger.info(
            "Saved content recommendation prompt_id=%s content_recommendation_id=%s company_id=%s table=%s",
            prompt_id,
            content_recommendation_id,
            company_id,
            _content_recommendation_table(),
        )
        return {
            "prompt_id": prompt_id,
            "content_recommendation_id": content_recommendation_id,
            "storage_error": None,
        }
    except Exception as exc:
        logger.exception("Failed to save content recommendation to Supabase")
        message = str(exc)
        table = _content_recommendation_table()
        if table.lower() in message.lower() or "PGRST205" in message or "does not exist" in message.lower():
            message = (
                f"{message} — Create the table in Supabase SQL Editor using "
                "db/migrations/007_content_recommendation.sql "
                f"(table name from SUPABASE_TABLE_CONTENT_RECOMMENDATION={table})"
            )
        return {
            "prompt_id": None,
            "content_recommendation_id": None,
            "storage_error": message,
        }


def _fetch_by_company_id_sync(company_id: str) -> dict[str, Any] | None:
    client = get_supabase()
    response = (
        client.table(_content_recommendation_table())
        .select(
            "id,prompt_id,company_id,company_name,created_at,success,status,summary,"
            "platforms,calendar_days,idea_count,ideas_count,calendar_items_count,"
            "duration_sec,result,content_calendar,content_ideas,recommendation,agent_type"
        )
        .eq("company_id", company_id)
        .eq("agent_type", AGENT_TYPE)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


async def get_content_recommendation(company_id: str) -> dict[str, Any] | None:
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
        client.table(_content_recommendation_table())
        .select(
            "id,prompt_id,company_id,company_name,created_at,success,status,summary,"
            "platforms,calendar_days,ideas_count,calendar_items_count,duration_sec,agent_type"
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


async def list_content_recommendations(
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


def _resolve_content_recommendation_id_sync(
    *,
    company_id: str | None = None,
    content_recommendation_id: str | None = None,
) -> str:
    client = get_supabase()
    table = _content_recommendation_table()

    if content_recommendation_id:
        response = (
            client.table(table)
            .select("id")
            .eq("id", content_recommendation_id.strip())
            .eq("agent_type", AGENT_TYPE)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise LookupError(f"Content recommendation not found: {content_recommendation_id}")
        return str(rows[0]["id"])

    company_id = (company_id or "").strip()
    if not company_id:
        raise ValueError("company_id or content_recommendation_id is required")

    response = (
        client.table(table)
        .select("id")
        .eq("company_id", company_id)
        .eq("agent_type", AGENT_TYPE)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise LookupError(f"Content recommendation not found for company_id: {company_id}")
    return str(rows[0]["id"])


def _delete_content_recommendation_sync(content_recommendation_id: str) -> dict[str, Any]:
    client = get_supabase()
    table = _content_recommendation_table()
    prompts_table = _prompts_table()

    existing = (
        client.table(table)
        .select("id,prompt_id,company_id,agent_type")
        .eq("id", content_recommendation_id)
        .eq("agent_type", AGENT_TYPE)
        .limit(1)
        .execute()
    )
    rows = existing.data or []
    if not rows:
        raise LookupError(f"Content recommendation not found: {content_recommendation_id}")

    row = rows[0]
    prompt_id = row.get("prompt_id")
    company_id = row.get("company_id")

    delete_resp = (
        client.table(table)
        .delete()
        .eq("id", content_recommendation_id)
        .eq("agent_type", AGENT_TYPE)
        .execute()
    )
    if not (delete_resp.data or []):
        check = (
            client.table(table)
            .select("id")
            .eq("id", content_recommendation_id)
            .limit(1)
            .execute()
        )
        if check.data:
            raise RuntimeError(
                f"Failed to delete content recommendation row: {content_recommendation_id}"
            )

    deleted_prompt = False
    if prompt_id:
        remaining = (
            client.table(table)
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
        "content_recommendation_id": content_recommendation_id,
        "prompt_id": prompt_id,
        "company_id": company_id,
        "deleted_prompt": deleted_prompt,
    }


async def delete_content_recommendation(
    *,
    company_id: str | None = None,
    content_recommendation_id: str | None = None,
) -> dict[str, Any]:
    if not _is_storage_configured():
        raise RuntimeError("Supabase is not configured")

    resolved_id = await asyncio.to_thread(
        _resolve_content_recommendation_id_sync,
        company_id=company_id,
        content_recommendation_id=content_recommendation_id,
    )
    result = await asyncio.to_thread(_delete_content_recommendation_sync, resolved_id)
    logger.info(
        "Deleted content recommendation id=%s company_id=%s prompt_id=%s prompt_deleted=%s",
        result.get("content_recommendation_id"),
        result.get("company_id"),
        result.get("prompt_id"),
        result.get("deleted_prompt"),
    )
    return {"success": True, **result}
