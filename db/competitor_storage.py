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
    return (config.SUPABASE_TABLE_COMPETITORSANALYSIS or "competitorsanalysis").strip()


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
    company_name: str | None = None,
    region: str | None = None,
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
        "platform": meta.get("platform") or "competitor",
        "company_name": company_name,
        "region": region,
    }
    response = client.table(_analysis_table()).insert(row).execute()
    data = response.data or []
    if not data:
        raise RuntimeError(
            f"Supabase returned no row after insert into {_analysis_table()}. "
            "Create the table with db/migrations/004_competitorsanalysis.sql"
        )
    return str(data[0]["id"])


async def save_competitor_run(
    request: CompetitorAnalysisRequest,
    result: dict[str, Any],
    *,
    duration_sec: float,
) -> dict[str, str | None]:
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
        company = request.normalized_company()
        analysis_id = await asyncio.to_thread(
            _insert_analysis_sync,
            prompt_id=prompt_id,
            result=result,
            duration_sec=duration_sec,
            company_name=company.get("name") or request.company_name,
            region=request.region,
        )
        logger.info(
            "Saved competitor run prompt_id=%s analysis_id=%s table=%s",
            prompt_id,
            analysis_id,
            _analysis_table(),
        )
        return {"prompt_id": prompt_id, "analysis_id": analysis_id, "storage_error": None}
    except Exception as exc:
        logger.exception("Failed to save competitor run to Supabase")
        message = str(exc)
        if "competitorsanalysis" in message.lower() or "PGRST205" in message or "does not exist" in message.lower():
            message = (
                f"{message} — Create the table in Supabase SQL Editor using "
                "db/migrations/004_competitorsanalysis.sql "
                f"(table name from SUPABASE_TABLE_COMPETITORSANALYSIS={_analysis_table()})"
            )
        return {
            "prompt_id": None,
            "analysis_id": None,
            "storage_error": message,
        }


def _reports_table() -> str:
    return (config.SUPABASE_TABLE_REPORTS or "reports").strip()


def _delete_analysis_sync(analysis_id: str) -> dict[str, Any]:
    client = get_supabase()
    analysis_table = _analysis_table()
    prompts_table = _prompts_table()
    reports_table = _reports_table()

    existing = (
        client.table(analysis_table)
        .select("id,prompt_id,agent_type")
        .eq("id", analysis_id)
        .eq("agent_type", AGENT_TYPE)
        .limit(1)
        .execute()
    )
    rows = existing.data or []
    if not rows:
        raise LookupError(f"Analysis not found: {analysis_id}")

    prompt_id = rows[0].get("prompt_id")
    deleted_reports = 0
    deleted_prompt = False

    try:
        reports_resp = (
            client.table(reports_table)
            .delete()
            .eq("analysis_id", analysis_id)
            .execute()
        )
        deleted_reports = len(reports_resp.data or [])
    except Exception:
        logger.warning(
            "Failed deleting reports for analysis_id=%s (table may not exist)",
            analysis_id,
            exc_info=True,
        )

    analysis_resp = (
        client.table(analysis_table)
        .delete()
        .eq("id", analysis_id)
        .eq("agent_type", AGENT_TYPE)
        .execute()
    )
    if not (analysis_resp.data or []):
        check = (
            client.table(analysis_table)
            .select("id")
            .eq("id", analysis_id)
            .limit(1)
            .execute()
        )
        if check.data:
            raise RuntimeError(f"Failed to delete analysis row: {analysis_id}")

    if prompt_id:
        remaining = (
            client.table(analysis_table)
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
        "analysis_id": analysis_id,
        "prompt_id": prompt_id,
        "deleted_reports": deleted_reports,
        "deleted_prompt": deleted_prompt,
    }


async def delete_competitor_analysis(analysis_id: str) -> dict[str, Any]:
    if not _is_storage_configured():
        raise RuntimeError("Supabase is not configured")

    result = await asyncio.to_thread(_delete_analysis_sync, analysis_id)
    logger.info(
        "Deleted competitor analysis analysis_id=%s prompt_id=%s reports=%s prompt_deleted=%s",
        result.get("analysis_id"),
        result.get("prompt_id"),
        result.get("deleted_reports"),
        result.get("deleted_prompt"),
    )
    return result
