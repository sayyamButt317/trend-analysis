from __future__ import annotations
import logging
import time
from datetime import datetime, timezone
from typing import Any
from agents.analyzecompany.graph.company_graph import analyze_company_app
from agents.analyzecompany.pipeline_log import log_event, log_pipeline_complete, log_pipeline_start
from agents.analyzecompany.response import build_slim_analyze_company_response
from agents.analyzecompany.schemas.company_request import AnalyzeCompanyRequest
from agents.analyzecompany.state.companystate import AnalyzeCompanyState
from core.api_call_counter import begin_api_call_stats, end_api_call_stats
from db.company_storage import save_company_analysis_run
import logging

logger = logging.getLogger(__name__)


async def analyzeCompanyAgent(request: AnalyzeCompanyRequest) -> dict[str, Any]:
    start = time.time()
    begin_api_call_stats()
    config = request.to_agent_config()
    company = request.normalized_company()
    company_id = request.company_id

    logger.info(
        "Analyzing company: %s",
        company.get("name") or request.website_url or request.company_id,
    )

    log_pipeline_start(
        company=company.get("name") or request.website_url or "unknown",
        website=request.website_url or company.get("website") or "none",
        region=request.region,
        instagram=request.instagram_username or "none",
        linkedin="yes" if request.linkedin_url or company.get("linkedin_url") else "no",
        post_limit=config.get("post_limit"),
    )

    initial_state: AnalyzeCompanyState = {
        "config": config,
        "company_profile": {},
        "company_analysis": {},
        "company_posts": [],
        "linkedin_posts": [],
        "web_crawl": {},
        "discovery_features": {},
        "company_summary": {},
        "company_summary_text": "",
        "warnings": [],
        "error": None,
    }

    result: dict[str, Any]
    duration = 0.0

    try:
        try:
            final_state = await analyze_company_app.ainvoke(initial_state)
        except Exception as exc:
            duration = round(time.time() - start, 3)
            api_calls = end_api_call_stats()
            log_pipeline_complete(status="failed", duration_sec=duration, error=str(exc)[:160])
            result = build_slim_analyze_company_response(
                success=False,
                error=str(exc),
                company=company,
                company_summary={},
                meta={
                    "status": "failed",
                    "duration_sec": duration,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent_mode": "analyze_company",
                    "company_id": company_id,
                    "api_call_breakdown": api_calls.get("breakdown") or {},
                },
            )
        else:
            duration = round(time.time() - start, 3)
            api_calls = end_api_call_stats()
            error = final_state.get("error")
            summary = final_state.get("company_summary") or {}
            profile = final_state.get("company_profile") or company
            analysis = final_state.get("company_analysis") or {}
            success = not error and bool(summary.get("summary_text") or summary.get("brief"))
            status = "success" if success else "failed"

            log_pipeline_complete(
                status=status,
                duration_sec=duration,
                company=(summary.get("brief") or {}).get("name") or profile.get("name"),
                error=(str(error)[:120] if error else None),
            )
            log_event("9_complete", "Slim result ready", success=success)

            result = build_slim_analyze_company_response(
                success=success,
                error=error,
                company=profile,
                company_profile=profile,
                company_analysis=analysis,
                company_summary=summary,
                intelligence={
                    "executive_snapshot": final_state.get("executive_snapshot") or {},
                    "digital_presence": final_state.get("digital_presence") or {},
                    "market_position": final_state.get("market_position") or {},
                    "positioning_analysis": final_state.get("positioning_analysis") or {},
                    "strengths_and_weaknesses": final_state.get("strengths_and_weaknesses") or {},
                    "growth_opportunities": final_state.get("growth_opportunities") or [],
                    "recommended_actions": final_state.get("recommended_actions") or [],
                },
                warnings=final_state.get("warnings") or [],
                meta={
                    "status": status,
                    "duration_sec": duration,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent_mode": "analyze_company",
                    "company_id": company_id,
                    "tavily_calls": api_calls.get("tavily_calls", 0),
                    "instagram_calls": api_calls.get("instagram_calls", 0),
                    "linkedin_calls": api_calls.get("linkedin_calls", 0),
                    "firecrawl_calls": api_calls.get("firecrawl_calls", 0),
                    "api_call_breakdown": api_calls.get("breakdown") or {},
                },
            )
    finally:
        pass

    storage_ids = await save_company_analysis_run(request, result, duration_sec=duration)
    result.setdefault("meta", {})
    result["meta"]["prompt_id"] = storage_ids.get("prompt_id")
    result["meta"]["analysis_id"] = storage_ids.get("analysis_id")
    if storage_ids.get("storage_error"):
        result["meta"]["storage_error"] = storage_ids["storage_error"]
    return result
