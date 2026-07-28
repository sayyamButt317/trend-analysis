import asyncio
import logging
from typing import Any

from agents.trend.schemas.competitor_request import CompetitorAnalysisRequest
from config.credential_config import config, resolve_supabase_api_key
from db.connection import get_supabase

logger = logging.getLogger(__name__)

AGENT_TYPE = "competitor"


def _is_storage_configured() -> bool:
    return bool((config.SUPABASE_URL or "").strip() and resolve_supabase_api_key())


def _prompts_table() -> str:
    return (config.SUPABASE_TABLE_PROMPTS or "prompts").strip()


def _analysis_table() -> str:
    return (config.SUPABASE_TABLE_ANALYSIS or "analysis").strip()


def _insert_prompt_sync(request: CompetitorAnalysisRequest) -> str:
    client = get_supabase()
    company = request.normalized_company()
    row = {
        "agent_type": AGENT_TYPE,
        "company_data": request.company_data,
        "region": request.region,
        "company_name": company.get("name"),
        "competitors": request.competitors or [],
        "request_payload": request.model_dump(mode="json"),
    }
    response = client.table(_prompts_table()).insert(row).execute()
    data = response.data or []
    if not data:
        raise RuntimeError("Supabase returned no prompt row after insert")
    return str(data[0]["id"])


def _insert_analysis_sync(
    *,
    prompt_id: str,
    result: dict[str, Any],
    duration_sec: float,
) -> str:
    client = get_supabase()
    meta = result.get("meta") or {}
    row = {
        "prompt_id": prompt_id,
        "agent_type": AGENT_TYPE,
        "status": meta.get("status") or ("success" if result.get("success") else "failed"),
        "success": bool(result.get("success")),
        "error": result.get("error"),
        "summary": result.get("summary"),
        "result": result,
        "competitor_count": int(result.get("competitor_count") or 0),
        "post_count": int(result.get("post_count") or 0),
        "duration_sec": round(duration_sec, 3),
        "platform": meta.get("platform"),
    }
    response = client.table(_analysis_table()).insert(row).execute()
    data = response.data or []
    if not data:
        raise RuntimeError("Supabase returned no analysis row after insert")
    return str(data[0]["id"])


async def save_competitor_run(
    request: CompetitorAnalysisRequest,
    result: dict[str, Any],
    *,
    duration_sec: float,
) -> dict[str, str | None]:
    """Persist user input to prompts and API result to analysis."""
    if not _is_storage_configured():
        message = (
            "Supabase storage skipped: use SUPABASE_SERVICE_ROLE_KEY (JWT) from "
            "Supabase Dashboard → API. sb_publishable_ keys are not supported."
        )
        if (config.SUPABASE_KEY or "").startswith("sb_publishable_"):
            logger.warning(message)
            return {"prompt_id": None, "analysis_id": None, "storage_error": message}
        logger.warning("Supabase not configured; skipping prompts/analysis persistence")
        return {"prompt_id": None, "analysis_id": None, "storage_error": "Supabase not configured"}

    try:
        prompt_id = await asyncio.to_thread(_insert_prompt_sync, request)
        analysis_id = await asyncio.to_thread(
            _insert_analysis_sync,
            prompt_id=prompt_id,
            result=result,
            duration_sec=duration_sec,
        )
        logger.info(
            "Saved competitor run prompt_id=%s analysis_id=%s",
            prompt_id,
            analysis_id,
        )
        return {"prompt_id": prompt_id, "analysis_id": analysis_id, "storage_error": None}
    except Exception as exc:
        logger.exception("Failed to save competitor run to Supabase")
        return {
            "prompt_id": None,
            "analysis_id": None,
            "storage_error": str(exc),
        }
