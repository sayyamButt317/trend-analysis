from __future__ import annotations

import logging

from agents.contentrecommendation.state.contentstate import ContentState
from service.ContentRecommendation.builder import build_platform_strategy

logger = logging.getLogger(__name__)


async def GeneratePlatformStrategyNode(state: ContentState) -> ContentState:
    try:
        config = state.get("config") or {}
        state["platform_strategy"] = build_platform_strategy(
            platforms=state.get("platforms") or config.get("platforms") or ["linkedin", "instagram"],
            content_strategy=state.get("content_strategy") or {},
            social_performance=state.get("social_performance") or {},
        )
        state.setdefault("logs", []).append("Platform strategy generated.")
        return state
    except Exception as exc:
        logger.exception("Platform strategy generation failed")
        state["error"] = f"Platform strategy generation failed: {exc}"
        return state
