from __future__ import annotations

import logging

from agents.contentrecommendation.state.contentstate import ContentState
from service.ContentRecommendation.builder import build_content_ideas

logger = logging.getLogger(__name__)


def _flatten_opportunities(content_opportunities: dict) -> dict:
    if not isinstance(content_opportunities, dict):
        return {"opportunities": []}
    if isinstance(content_opportunities.get("opportunities"), list):
        return content_opportunities

    merged: list[dict] = []
    for value in content_opportunities.values():
        if not isinstance(value, dict):
            continue
        for row in value.get("opportunities") or []:
            if isinstance(row, dict):
                merged.append(row)
    merged.sort(key=lambda row: int(row.get("priority") or 0), reverse=True)
    return {"opportunities": merged}


async def GenerateContentIdeasNode(state: ContentState) -> ContentState:
    try:
        config = state.get("config") or {}
        idea_count = int(config.get("idea_count") or 10)
        state["content_ideas"] = await build_content_ideas(
            company=state.get("company") or config.get("company") or {},
            opportunities=_flatten_opportunities(state.get("content_opportunities") or {}),
            content_strategy=state.get("content_strategy") or {},
            platform_strategy=state.get("platform_strategy") or {},
            platforms=state.get("platforms") or config.get("platforms") or ["linkedin", "instagram"],
            idea_count=idea_count,
        )
        state.setdefault("logs", []).append(
            f"Content ideas generated ({len(state.get('content_ideas') or [])})."
        )
        return state
    except Exception as exc:
        logger.exception("Content ideas generation failed")
        state["error"] = f"Content ideas generation failed: {exc}"
        return state
