import time
from datetime import datetime, timezone
from typing import Any

from agents.trend.graph.trendgraph import trend_graph_app
from agents.trend.state.trend_state import TrendState


async def trendInvoke(config: dict[str, Any] | None = None) -> TrendState:
    start_time = time.time()
    initial_state: TrendState = {
        "config": {
            "platform": "instagram",
            "country": "United Arab Emirates",
            "category": None,
            "seed_usernames": None,
            "auto_discover": True,
            "use_database": False,
            "influencer_limit": 20,
            "request_delay_seconds": 1.0,
            "min_engagement_rate": 1.0,
            **(config or {}),
        },
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
        "trend_summary": "",
    }

    try:
        final_state = await trend_graph_app.ainvoke(initial_state)
        post_count = len(final_state.get("processed_posts") or [])
        has_error = bool(final_state.get("error"))
        final_state["_meta"] = {
            "status": (
                "success"
                if not has_error and post_count > 0
                else "partial" if post_count > 0 else "failed"
            ),
            "duration_sec": round(time.time() - start_time, 3),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "platform": final_state.get("config", {}).get("platform"),
            "discovery_source": final_state.get("config", {}).get("discovery_source"),
        }
        return {
            "success": not has_error and post_count > 0,
            "error": final_state.get("error"),
            "country": final_state.get("config", {}).get("country"),
            "category": final_state.get("config", {}).get("category"),
            "discovery_source": final_state.get("config", {}).get("discovery_source"),
            "discovered_influencers": final_state.get("discovered_influencers") or [],
            "post_count": post_count,
            "viral_posts": final_state.get("viral_posts") or [],
            "viral_sounds": final_state.get("viral_sounds") or [],
            "viral_categories": final_state.get("viral_categories") or [],
            "trend_summary": final_state.get("trend_summary") or "",
            "trend_scores": final_state.get("trend_scores") or [],
            "saved_trend_id": final_state.get("saved_trend_id"),
            "_meta": final_state.get("_meta"),
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "_meta": {
                "status": "failed",
                "duration_sec": round(time.time() - start_time, 3),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
