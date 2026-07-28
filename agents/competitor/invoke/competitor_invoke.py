import time
from datetime import datetime, timezone
from typing import Any

from agents.competitor.graph.competitor_graph import competitor_graph_app
from agents.trend.schemas.competitor_request import CompetitorAnalysisRequest
from agents.trend.services.competitor_response import build_competitor_response
from agents.trend.state.trend_state import TrendState
from db.competitor_storage import save_competitor_run


async def competitorAnalysisAgent(
    request: CompetitorAnalysisRequest,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    start_time = time.time()

    agent_config = {
        **request.to_agent_config(),
        "agent_mode": "competitor",
        "platform": "instagram",
        **(config or {}),
    }
    company_payload = agent_config.get("company") or request.normalized_company()
    filters_applied = agent_config.get("filters") or {"region": request.region}

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
    }

    try:
        final_state = await competitor_graph_app.ainvoke(initial_state)
        post_count = len(final_state.get("processed_posts") or [])
        has_error = bool(final_state.get("error"))
        duration_sec = round(time.time() - start_time, 3)
        meta = {
            "status": (
                "success"
                if not has_error and post_count > 0
                else "partial" if post_count > 0 else "failed"
            ),
            "duration_sec": duration_sec,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "platform": "instagram",
            "agent_mode": "competitor",
            "discovery_source": final_state.get("config", {}).get("discovery_source"),
        }

        result = build_competitor_response(
            company=company_payload,
            filters=final_state.get("config", {}).get("filters_applied") or filters_applied,
            competitors=final_state.get("discovered_influencers") or [],
            processed_posts=final_state.get("processed_posts") or [],
            content_mix=final_state.get("content_mix") or [],
            topics=final_state.get("topics") or [],
            hashtags=final_state.get("hashtags") or [],
            summary=final_state.get("competitor_summary") or "",
            meta=meta,
            error=final_state.get("error"),
        )
    except Exception as exc:
        duration_sec = round(time.time() - start_time, 3)
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
                "platform": "instagram",
                "agent_mode": "competitor",
            },
            error=str(exc),
        )

    storage_ids = await save_competitor_run(request, result, duration_sec=duration_sec)
    result.setdefault("meta", {})
    result["meta"]["prompt_id"] = storage_ids.get("prompt_id")
    result["meta"]["analysis_id"] = storage_ids.get("analysis_id")
    if storage_ids.get("storage_error"):
        result["meta"]["storage_error"] = storage_ids["storage_error"]
    return result
