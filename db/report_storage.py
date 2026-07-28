import asyncio
import logging
from typing import Any

from config.credential_config import config, resolve_supabase_api_key
from db.connection import get_supabase

logger = logging.getLogger(__name__)

AGENT_TYPE = "competitor"


def _reports_table() -> str:
    return (config.SUPABASE_TABLE_REPORTS or "reports").strip()


def _is_storage_configured() -> bool:
    return bool((config.SUPABASE_URL or "").strip() and resolve_supabase_api_key())


def _insert_report_sync(
    *,
    report_id: str,
    analysis_id: str,
    prompt_id: str,
    report: dict[str, Any],
) -> str:
    client = get_supabase()
    stats = report.get("stats") or {}
    input_data = report.get("input") or {}
    row = {
        "id": report_id,
        "analysis_id": analysis_id,
        "prompt_id": prompt_id,
        "agent_type": AGENT_TYPE,
        "title": report.get("title") or "Competitor Analysis Report",
        "company_name": input_data.get("company_name"),
        "region": input_data.get("region"),
        "executive_summary": report.get("executive_summary"),
        "report": report,
        "competitor_count": int(stats.get("competitor_count") or 0),
        "post_count": int(stats.get("post_count") or 0),
    }
    response = client.table(_reports_table()).insert(row).execute()
    data = response.data or []
    if not data:
        raise RuntimeError("Supabase returned no report row after insert")
    return str(data[0]["id"])


def _fetch_reports_sync(
    *,
    report_id: str | None = None,
    analysis_id: str | None = None,
) -> list[dict[str, Any]]:
    client = get_supabase()
    query = (
        client.table(_reports_table())
        .select(
            "id,analysis_id,prompt_id,title,company_name,region,"
            "executive_summary,competitor_count,post_count,created_at,report"
        )
        .eq("agent_type", AGENT_TYPE)
        .order("created_at", desc=True)
    )
    if report_id:
        query = query.eq("id", report_id)
    if analysis_id:
        query = query.eq("analysis_id", analysis_id)

    response = query.execute()
    return response.data or []


async def save_competitor_report(
    *,
    report_id: str,
    analysis_id: str,
    prompt_id: str,
    report: dict[str, Any],
) -> str:
    if not _is_storage_configured():
        raise RuntimeError("Supabase is not configured")

    saved_id = await asyncio.to_thread(
        _insert_report_sync,
        report_id=report_id,
        analysis_id=analysis_id,
        prompt_id=prompt_id,
        report=report,
    )
    logger.info(
        "Saved competitor report report_id=%s analysis_id=%s",
        saved_id,
        analysis_id,
    )
    return saved_id


async def fetch_stored_reports(
    *,
    report_id: str | None = None,
    analysis_id: str | None = None,
) -> list[dict[str, Any]]:
    if not _is_storage_configured():
        raise RuntimeError("Supabase is not configured")

    return await asyncio.to_thread(
        _fetch_reports_sync,
        report_id=report_id,
        analysis_id=analysis_id,
    )
