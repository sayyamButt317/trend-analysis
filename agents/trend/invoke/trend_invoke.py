import time
from datetime import datetime, timezone
from typing import Any

from agents.trend.graph.trendgraph import trend_graph_app
from agents.trend.schemas.trend_request import GlobalTrendRequest
from agents.trend.services.trend_response import build_trend_response
from agents.trend.state.trend_state import TrendState
from db.trend_storage import save_trend_run


async def globalTrendInvoke(
    request: GlobalTrendRequest | None = None,
) -> dict[str, Any]:
    start_time = time.time()
    request = request or GlobalTrendRequest()
    agent_config = request.to_agent_config()

    initial_state: TrendState = {
        "config": agent_config,
        "discovered_influencers": [],
        "discovered_posts": [],
        "raw_posts": [],
        "processed_posts": [],
        "hashtags": [],
        "audios": [],
        "audio_summary": [],
        "topics": [],
        "engagement_metrics": [],
        "viral_posts": [],
        "viral_sounds": [],
        "viral_categories": [],
        "trend_groups": [],
        "trend_scores": [],
        "content_mix": [],
        "web_crawl": {},
        "web_trends": {},
        "company_analysis": {},
        "company_posts": [],
        "linkedin_posts": [],
        "pain_points": [],
        "trend_summary": "",
    }

    try:
        final_state = await trend_graph_app.ainvoke(initial_state)
        web_trends = final_state.get("web_trends") or {}
        has_web = bool(
            web_trends.get("hashtags")
            or web_trends.get("reel_formats")
            or web_trends.get("google_trends")
        )
        has_error = bool(final_state.get("error")) and not has_web
        final_config = final_state.get("config") or agent_config

        meta = {
            "status": "success" if not has_error and has_web else "partial" if has_web else "failed",
            "duration_sec": round(time.time() - start_time, 3),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "platform": final_config.get("platform"),
            "discovery_source": final_config.get("discovery_source"),
            "agent_mode": "global_trend",
        }

        result = build_trend_response(
            company={},
            config=final_config,
            processed_posts=[],
            hashtags=final_state.get("hashtags") or [],
            topics=final_state.get("topics") or [],
            trend_scores=final_state.get("trend_scores") or [],
            viral_posts=[],
            viral_sounds=[],
            viral_categories=final_state.get("viral_categories") or [],
            content_mix=[],
            discovered_influencers=[],
            trend_summary=final_state.get("trend_summary") or "",
            meta=meta,
            web_trends=web_trends,
            web_crawl=final_state.get("web_crawl") or {},
            error=final_state.get("error") if has_error else None,
        )

        final_state["_meta"] = meta
        final_state["web_trends"] = web_trends
        save_result = await save_trend_run(final_state)
        result["saved_trend_id"] = save_result.get("trend_id")
        if save_result.get("storage_error"):
            result.setdefault("meta", {})["storage_error"] = save_result["storage_error"]
        return result
    except Exception as exc:
        return build_trend_response(
            company={},
            config=agent_config,
            processed_posts=[],
            hashtags=[],
            topics=[],
            trend_scores=[],
            viral_posts=[],
            viral_sounds=[],
            viral_categories=[],
            content_mix=[],
            discovered_influencers=[],
            trend_summary="",
            meta={
                "status": "failed",
                "duration_sec": round(time.time() - start_time, 3),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_mode": "global_trend",
            },
            error=str(exc),
        )


# Backward-compatible alias
async def trendInvoke(request: GlobalTrendRequest | None = None) -> dict[str, Any]:
    return await globalTrendInvoke(request)
