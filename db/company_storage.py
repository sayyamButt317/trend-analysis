import asyncio
import logging
from typing import Any

from agents.analyzecompany.schemas.company_request import AnalyzeCompanyRequest
from config.credential_config import config, resolve_supabase_api_key
from db.connection import get_supabase

logger = logging.getLogger(__name__)

AGENT_TYPE = "analyze_company"


def _is_storage_configured() -> bool:
    return bool((config.SUPABASE_URL or "").strip() and resolve_supabase_api_key())


def _prompts_table() -> str:
    return (config.SUPABASE_TABLE_PROMPTS or "prompts").strip()


def _analysis_table() -> str:
    return (config.SUPABASE_TABLE_ANALYSIS or "analysis").strip()


def _insert_prompt_sync(request: AnalyzeCompanyRequest) -> str:
    client = get_supabase()
    company = request.normalized_company()
    company_data = (
        request.company_data
        or (f"Website: {request.website_url}" if request.website_url else None)
        or company.get("description")
        or company.get("name")
        or "Company analysis"
    )
    row = {
        "agent_type": AGENT_TYPE,
        "company_data": company_data,
        "region": request.region or company.get("region") or "unspecified",
        "company_name": company.get("name"),
        "company_id": request.company_id,
        "competitors": [],
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
    company_id: str | None = None,
) -> str:
    client = get_supabase()
    meta = result.get("meta") or {}
    brief = ((result.get("company_summary") or {}).get("brief") or {})
    row = {
        "prompt_id": prompt_id,
        "agent_type": AGENT_TYPE,
        "company_id": company_id or meta.get("company_id"),
        "status": meta.get("status") or ("success" if result.get("success") else "failed"),
        "success": bool(result.get("success")),
        "error": result.get("error"),
        "summary": result.get("summary_text") or brief.get("name"),
        "result": result,
        "competitor_count": 0,
        "post_count": len(result.get("company_posts") or [])
        if isinstance(result.get("company_posts"), list)
        else 0,
        "duration_sec": round(duration_sec, 3),
        "platform": "company",
    }
    response = client.table(_analysis_table()).insert(row).execute()
    data = response.data or []
    if not data:
        raise RuntimeError("Supabase returned no analysis row after insert")
    return str(data[0]["id"])


async def save_company_analysis_run(
    request: AnalyzeCompanyRequest,
    result: dict[str, Any],
    *,
    duration_sec: float,
) -> dict[str, str | None]:
    """Persist analyze-company output into prompts + SUPABASE_TABLE_ANALYSIS."""
    if not _is_storage_configured():
        message = (
            "Supabase storage skipped: use SUPABASE_SERVICE_ROLE_KEY (JWT) from "
            "Supabase Dashboard → API. sb_publishable_ keys are not supported."
        )
        if (config.SUPABASE_KEY or "").startswith("sb_publishable_"):
            logger.warning(message)
            return {"prompt_id": None, "analysis_id": None, "storage_error": message}
        logger.warning("Supabase not configured; skipping company analysis persistence")
        return {"prompt_id": None, "analysis_id": None, "storage_error": "Supabase not configured"}

    try:
        prompt_id = await asyncio.to_thread(_insert_prompt_sync, request)
        analysis_id = await asyncio.to_thread(
            _insert_analysis_sync,
            prompt_id=prompt_id,
            result=result,
            duration_sec=duration_sec,
            company_id=request.company_id,
        )
        logger.info(
            "Saved company analysis prompt_id=%s analysis_id=%s table=%s",
            prompt_id,
            analysis_id,
            _analysis_table(),
        )
        return {"prompt_id": prompt_id, "analysis_id": analysis_id, "storage_error": None}
    except Exception as exc:
        logger.exception("Failed to save company analysis to Supabase")
        return {
            "prompt_id": None,
            "analysis_id": None,
            "storage_error": str(exc),
        }


def _fetch_company_analysis_sync(analysis_id: str) -> dict[str, Any] | None:
    client = get_supabase()
    response = (
        client.table(_analysis_table())
        .select("id,prompt_id,company_id,created_at,success,status,summary,result,agent_type,duration_sec")
        .eq("id", analysis_id)
        .eq("agent_type", AGENT_TYPE)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


async def get_company_analysis(analysis_id: str) -> dict[str, Any] | None:
    if not _is_storage_configured():
        raise RuntimeError("Supabase is not configured")
    return await asyncio.to_thread(_fetch_company_analysis_sync, analysis_id)


def _list_company_analyses_sync(*, limit: int = 20) -> list[dict[str, Any]]:
    client = get_supabase()
    response = (
        client.table(_analysis_table())
        .select("id,prompt_id,company_id,created_at,success,status,summary,agent_type,duration_sec")
        .eq("agent_type", AGENT_TYPE)
        .order("created_at", desc=True)
        .limit(max(1, min(limit, 100)))
        .execute()
    )
    return response.data or []


async def list_company_analyses(*, limit: int = 20) -> list[dict[str, Any]]:
    if not _is_storage_configured():
        raise RuntimeError("Supabase is not configured")
    return await asyncio.to_thread(_list_company_analyses_sync, limit=limit)
