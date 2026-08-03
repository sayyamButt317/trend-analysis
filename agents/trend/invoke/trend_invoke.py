import time
from datetime import datetime, timezone
from typing import Any

from agents.trend.graph.trendgraph import trend_graph_app
from agents.trend.schemas.trend_request import TrendDiscoveryRequest
from agents.trend.services.trend_response import build_trend_response
from agents.trend.state.trend_state import TrendState
from db.trend_storage import save_trend_run


async def trendInvoke(
    config: dict[str, Any] | TrendDiscoveryRequest | None = None,
) -> dict[str, Any]:
    start_time = time.time()

    if isinstance(config, TrendDiscoveryRequest):
        request = config
        agent_config = request.to_agent_config()
        company_payload = request.normalized_company()
    elif isinstance(config, dict) and (config.get("company_data") or config.get("region")):
        request = TrendDiscoveryRequest.model_validate(config)
        agent_config = request.to_agent_config()
        company_payload = request.normalized_company()
    elif config is None or config == {}:
        request = TrendDiscoveryRequest()
        agent_config = request.to_agent_config()
        company_payload = {}
    elif isinstance(config, dict):
        request = None
        agent_config = {
            "platform": "instagram",
            "include_web_trends": True,
            **config,
        }
        company_payload = agent_config.get("company") or {}
    else:
        request = TrendDiscoveryRequest()
        agent_config = request.to_agent_config()
        company_payload = {}

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
        post_count = len(final_state.get("processed_posts") or [])
        web_trends = final_state.get("web_trends") or {}
        has_web = bool(
            web_trends.get("hashtags")
            or web_trends.get("reel_formats")
            or web_trends.get("google_trends")
        )
        has_error = bool(final_state.get("error")) and not has_web and post_count == 0
        final_config = final_state.get("config") or agent_config

        meta = {
            "status": (
                "success"
                if not has_error and (post_count > 0 or has_web)
                else "partial"
                if post_count > 0 or has_web
                else "failed"
            ),
            "duration_sec": round(time.time() - start_time, 3),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "platform": final_config.get("platform"),
            "discovery_source": final_config.get("discovery_source"),
            "agent_mode": final_config.get("agent_mode") or (request.mode if request else "trend"),
        }

        result = build_trend_response(
            company=company_payload or final_config.get("company") or {},
            config=final_config,
            processed_posts=final_state.get("processed_posts") or [],
            hashtags=final_state.get("hashtags") or [],
            topics=final_state.get("topics") or [],
            trend_scores=final_state.get("trend_scores") or [],
            viral_posts=final_state.get("viral_posts") or [],
            viral_sounds=final_state.get("viral_sounds") or [],
            viral_categories=final_state.get("viral_categories") or [],
            content_mix=final_state.get("content_mix") or [],
            discovered_influencers=final_state.get("discovered_influencers") or [],
            trend_summary=final_state.get("trend_summary") or "",
            meta=meta,
            web_trends=web_trends,
            web_crawl=final_state.get("web_crawl") or {},
            company_analysis=final_state.get("company_analysis") or {},
            company_posts=final_state.get("company_posts") or [],
            linkedin_posts=final_state.get("linkedin_posts") or [],
            pain_points=final_state.get("pain_points") or [],
            error=final_state.get("error") if has_error else None,
        )

        final_state["_meta"] = meta
        final_state["competitor_strategies"] = result.get("competitor_strategies")
        final_state["market_insights"] = result.get("market_insights")
        final_state["company"] = result.get("company")
        final_state["web_trends"] = web_trends

        save_result = await save_trend_run(final_state)
        result["saved_trend_id"] = save_result.get("trend_id")
        if save_result.get("storage_error"):
            result.setdefault("meta", {})["storage_error"] = save_result["storage_error"]
        return result
    except Exception as exc:
        return build_trend_response(
            company=company_payload,
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
                "agent_mode": agent_config.get("agent_mode") or (request.mode if request else "trend"),
            },
            error=str(exc),
        )
