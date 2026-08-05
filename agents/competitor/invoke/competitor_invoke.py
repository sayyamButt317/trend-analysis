import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from agents.competitor.graph.competitor_graph import competitor_graph_app
from agents.competitor.pipeline_log import log_event, log_pipeline_complete, log_pipeline_start
from agents.trend.schemas.competitor_request import CompetitorAnalysisRequest
from agents.trend.services.competitor_response import build_competitor_response
from agents.trend.state.trend_state import TrendState
from core.api_call_counter import begin_api_call_stats, end_api_call_stats
from core.runtime import runtime_profile
from db.competitor_storage import save_competitor_run

logger = logging.getLogger("competitor.pipeline")


def _attach_api_call_meta(meta: dict[str, Any], api_calls: dict[str, Any]) -> dict[str, Any]:
    meta.update(
        {
            "tavily_calls": api_calls.get("tavily_calls", 0),
            "instagram_calls": api_calls.get("instagram_calls", 0),
            "linkedin_calls": api_calls.get("linkedin_calls", 0),
            "firecrawl_calls": api_calls.get("firecrawl_calls", 0),
            "api_call_breakdown": api_calls.get("breakdown") or {},
        }
    )
    return meta


async def competitorAnalysisAgent(
    request: CompetitorAnalysisRequest,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    start_time = time.time()
    begin_api_call_stats()

    agent_config = {
        **request.to_agent_config(),
        "agent_mode": "competitor",
        "platforms": ["instagram", "linkedin"],
        **(config or {}),
    }
    profile = agent_config.get("runtime_profile") or runtime_profile()
    max_duration = profile.get("max_duration_sec")
    company_payload = agent_config.get("company") or request.normalized_company()
    filters_applied = agent_config.get("filters") or {"region": request.region}

    company_name = (company_payload.get("name") or request.company_name or "Company").strip()
    ig_user = (
        company_payload.get("instagram_username")
        or agent_config.get("company_instagram_username")
        or ""
    ).strip().lstrip("@")
    log_pipeline_start(
        company=company_name,
        region=filters_applied.get("region"),
        city=filters_applied.get("city"),
        instagram=ig_user or "none",
        competitor_limit=agent_config.get("competitor_limit"),
        post_limit=agent_config.get("post_limit"),
        skip_linkedin=bool(agent_config.get("skip_linkedin")),
    )

    initial_state: TrendState = {
        "config": agent_config,
        "discovered_influencers": [],
        "discovered_posts": [],
        "raw_posts": [],
        "processed_posts": [],
        "hashtags": [],
        "topics": [],
        "engagement_metrics": [],
        "content_mix": [],
        "competitor_summary": "",
        "trend_summary": "",
        "company_profile": {},
        "search_intelligence": {},
        "discovery_candidates": [],
        "verified_competitors": [],
        "similarity_scores": [],
        "competitor_website_intel": [],
        "gap_analysis": {},
        "competitor_intelligence_report": {},
        "recommendations": [],
        "ai_report": {},
    }

    result: dict[str, Any]
    try:
        try:
            invoke = competitor_graph_app.ainvoke(initial_state)
            if max_duration:
                final_state = await asyncio.wait_for(invoke, timeout=float(max_duration))
            else:
                final_state = await invoke
            post_count = len(final_state.get("processed_posts") or [])
            has_error = bool(final_state.get("error"))
            duration_sec = round(time.time() - start_time, 3)
            final_competitors = (
                final_state.get("discovered_influencers")
                or final_state.get("competitors")
                or final_state.get("verified_competitors")
                or []
            )
            competitor_count = len(final_competitors)
            if has_error and competitor_count == 0:
                run_status = "failed"
            elif post_count > 0 and not has_error:
                run_status = "success"
            elif competitor_count > 0:
                run_status = "partial" if has_error or post_count == 0 else "success"
            else:
                run_status = "failed"
            meta = {
                "status": run_status,
                "duration_sec": duration_sec,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "platforms": ["instagram", "linkedin"],
                "agent_mode": "competitor",
                "discovery_source": final_state.get("config", {}).get("discovery_source"),
                "serverless": bool(profile.get("serverless")),
                "competitor_limit": agent_config.get("competitor_limit"),
                "post_limit": agent_config.get("post_limit"),
                "skip_linkedin": bool(agent_config.get("skip_linkedin")),
            }

            log_pipeline_complete(
                status=meta["status"],
                duration_sec=duration_sec,
                competitors=competitor_count,
                posts=post_count,
                error=str(final_state.get("error") or "")[:120] or None,
            )
            result = build_competitor_response(
                company=company_payload,
                filters=final_state.get("config", {}).get("filters_applied") or filters_applied,
                competitors=final_competitors,
                processed_posts=final_state.get("processed_posts") or [],
                content_mix=final_state.get("content_mix") or [],
                topics=final_state.get("topics") or [],
                hashtags=final_state.get("hashtags") or [],
                summary=final_state.get("competitor_summary") or "",
                meta=meta,
                error=final_state.get("error"),
                company_profile=final_state.get("company_profile"),
                search_intelligence=final_state.get("search_intelligence"),
                gap_analysis=final_state.get("gap_analysis"),
                competitor_intelligence_report=final_state.get("competitor_intelligence_report"),
                recommendations=final_state.get("recommendations"),
                ai_report=final_state.get("ai_report"),
                similarity_scores=final_state.get("similarity_scores"),
                company_analysis=final_state.get("company_analysis"),
                competitor_website_intel=final_state.get("competitor_website_intel"),
                web_crawl=final_state.get("web_crawl"),
            )
        except asyncio.TimeoutError:
            duration_sec = round(time.time() - start_time, 3)
            log_pipeline_complete(
                status="timed_out",
                duration_sec=duration_sec,
                limit_sec=max_duration,
            )
            limit = agent_config.get("competitor_limit")
            result = build_competitor_response(
                company=company_payload,
                filters=filters_applied,
                competitors=[],
                processed_posts=[],
                content_mix=[],
                topics=[],
                hashtags=[],
                summary="",
                meta={
                    "status": "failed",
                    "duration_sec": duration_sec,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "platforms": ["instagram", "linkedin"],
                    "agent_mode": "competitor",
                    "serverless": bool(profile.get("serverless")),
                },
                error=(
                    f"Analysis exceeded the {max_duration}s time limit. "
                    f"Retry with fewer competitors (current limit: {limit})."
                ),
            )
        except Exception as exc:
            duration_sec = round(time.time() - start_time, 3)
            logger.exception(
                "[Competitor 0_request] Pipeline run failed | duration_sec=%.2f",
                duration_sec,
            )
            result = build_competitor_response(
                company=company_payload,
                filters=filters_applied,
                competitors=[],
                processed_posts=[],
                content_mix=[],
                topics=[],
                hashtags=[],
                summary="",
                meta={
                    "status": "failed",
                    "duration_sec": duration_sec,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "platforms": ["instagram", "linkedin"],
                    "agent_mode": "competitor",
                },
                error=str(exc),
            )
    finally:
        api_calls = end_api_call_stats()
        result.setdefault("meta", {})
        _attach_api_call_meta(result["meta"], api_calls)
        log_event(
            "9_complete",
            "API call totals",
            tavily=api_calls.get("tavily_calls", 0),
            instagram=api_calls.get("instagram_calls", 0),
            linkedin=api_calls.get("linkedin_calls", 0),
            firecrawl=api_calls.get("firecrawl_calls", 0),
        )

    storage_ids = await save_competitor_run(request, result, duration_sec=duration_sec)
    result.setdefault("meta", {})
    result["meta"]["prompt_id"] = storage_ids.get("prompt_id")
    result["meta"]["analysis_id"] = storage_ids.get("analysis_id")
    if storage_ids.get("storage_error"):
        result["meta"]["storage_error"] = storage_ids["storage_error"]
    return result
