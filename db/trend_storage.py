import asyncio
import logging
from typing import Any
from config.credential_config import config, resolve_supabase_api_key
from db.connection import get_supabase

logger = logging.getLogger(__name__)

AGENT_TYPE = "trend"


def _is_storage_configured() -> bool:
    return bool((config.SUPABASE_URL or "").strip() and resolve_supabase_api_key())


def _trends_table() -> str:
    return (config.SUPABASE_TABLE_TRENDS or "trends").strip()


def _insert_trend_sync(state: dict[str, Any]) -> str:
    client = get_supabase()
    cfg = state.get("config") or {}
    meta = state.get("_meta") or {}
    post_count = len(state.get("processed_posts") or [])
    has_error = bool(state.get("error"))

    row = {
        "agent_type": AGENT_TYPE,
        "status": meta.get("status")
        or ("success" if not has_error and post_count > 0 else "failed"),
        "success": not has_error and post_count > 0,
        "error": state.get("error"),
        "platform": cfg.get("platform") or "instagram",
        "country": cfg.get("country"),
        "category": cfg.get("category"),
        "discovery_source": cfg.get("discovery_source"),
        "summary": state.get("trend_summary") or "",
        "post_count": post_count,
        "viral_post_count": len(state.get("viral_posts") or []),
        "duration_sec": meta.get("duration_sec"),
        "discovered_influencers": state.get("discovered_influencers") or [],
        "hashtags": state.get("hashtags") or [],
        "topics": state.get("topics") or [],
        "trend_scores": state.get("trend_scores") or [],
        "trend_groups": state.get("trend_groups") or [],
        "viral_posts": state.get("viral_posts") or [],
        "viral_sounds": state.get("viral_sounds") or [],
        "viral_categories": state.get("viral_categories") or [],
        "audio_summary": state.get("audio_summary") or [],
        "config": cfg,
        "result": {
            "mode": cfg.get("agent_mode"),
            "company": state.get("company") or cfg.get("company"),
            "competitor_strategies": state.get("competitor_strategies"),
            "market_insights": state.get("market_insights"),
            "web_trends": state.get("web_trends") or {},
            "web_sources": cfg.get("web_sources") or [],
            "trend_summary": state.get("trend_summary") or "",
            "trend_scores": state.get("trend_scores") or [],
            "trend_groups": state.get("trend_groups") or [],
            "viral_posts": state.get("viral_posts") or [],
            "viral_sounds": state.get("viral_sounds") or [],
            "viral_categories": state.get("viral_categories") or [],
            "discovered_influencers": state.get("discovered_influencers") or [],
            "hashtags": state.get("hashtags") or [],
            "topics": state.get("topics") or [],
            "audio_summary": state.get("audio_summary") or [],
            "processed_posts": state.get("processed_posts") or [],
            "meta": meta,
        },
    }

    prompt_id = cfg.get("prompt_id")
    if prompt_id:
        row["prompt_id"] = prompt_id

    response = client.table(_trends_table()).insert(row).execute()
    data = response.data or []
    if not data:
        raise RuntimeError("Supabase returned no trend row after insert")
    return str(data[0]["id"])


async def save_trend_run(state: dict[str, Any]) -> dict[str, str | None]:
    if not _is_storage_configured():
        message = (
            "Supabase storage skipped: use SUPABASE_SERVICE_ROLE_KEY (JWT) from "
            "Supabase Dashboard → API. sb_publishable_ keys are not supported."
        )
        if (config.SUPABASE_KEY or "").startswith("sb_publishable_"):
            logger.warning(message)
            return {"trend_id": None, "storage_error": message}
        logger.warning("Supabase not configured; skipping trends persistence")
        return {"trend_id": None, "storage_error": "Supabase not configured"}

    try:
        trend_id = await asyncio.to_thread(_insert_trend_sync, state)
        logger.info("Saved trend run trend_id=%s", trend_id)
        return {"trend_id": trend_id, "storage_error": None}
    except Exception as exc:
        logger.exception("Failed to save trend run to Supabase")
        return {"trend_id": None, "storage_error": str(exc)}
