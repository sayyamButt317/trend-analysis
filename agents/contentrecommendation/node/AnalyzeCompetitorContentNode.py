from __future__ import annotations

import logging

from agents.contentrecommendation.state.contentstate import ContentState
from service.ContentRecommendation.builder import build_competitor_content

logger = logging.getLogger(__name__)


async def AnalyzeCompetitorContentNode(state: ContentState) -> ContentState:
    try:
        config = state.get("config") or {}
        competitor_analysis = state.get("competitor_analysis") or config.get("competitor_analysis") or {}
        content_intelligence = (
            state.get("content_intelligence_input")
            or config.get("content_intelligence")
            or {}
        )
        state["competitor_content"] = build_competitor_content(
            competitor_analysis=competitor_analysis,
            content_intelligence=content_intelligence,
        )
        state.setdefault("logs", []).append("Competitor content patterns analyzed.")
        return state
    except Exception as exc:
        logger.exception("Competitor content analysis failed")
        state["error"] = f"Competitor content analysis failed: {exc}"
        return state
