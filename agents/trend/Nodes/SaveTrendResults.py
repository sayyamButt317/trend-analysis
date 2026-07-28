from datetime import datetime, timezone

from agents.trend.state.trend_state import TrendState
from app.db.connection import get_db


async def SaveTrendResultsNode(state: TrendState) -> TrendState:
    db = get_db()
    config = state.get("config") or {}
    collection_name = config.get("results_collection") or "instagram_trends"
    collection = db.get_collection(collection_name)

    document = {
        "platform": config.get("platform") or "instagram",
        "country": config.get("country"),
        "discovery_source": config.get("discovery_source"),
        "created_at": datetime.now(timezone.utc),
        "summary": state.get("trend_summary") or "",
        "post_count": len(state.get("processed_posts") or []),
        "viral_post_count": len(state.get("viral_posts") or []),
        "discovered_influencers": state.get("discovered_influencers") or [],
        "hashtags": state.get("hashtags") or [],
        "topics": state.get("topics") or [],
        "trend_scores": state.get("trend_scores") or [],
        "viral_posts": state.get("viral_posts") or [],
        "viral_sounds": state.get("viral_sounds") or [],
        "viral_categories": state.get("viral_categories") or [],
        "audio_summary": state.get("audio_summary") or [],
        "config": config,
    }
    result = await collection.insert_one(document)
    state["saved_trend_id"] = str(result.inserted_id)
    return state
