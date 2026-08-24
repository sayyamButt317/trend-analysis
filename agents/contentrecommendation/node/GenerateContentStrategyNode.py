from __future__ import annotations

import logging

from agents.contentrecommendation.state.contentstate import ContentState
from service.ContentRecommendation.builder import build_content_strategy

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


async def GenerateContentStrategyNode(state: ContentState) -> ContentState:
    try:
        config = state.get("config") or {}
        state["content_strategy"] = build_content_strategy(
            company=state.get("company") or config.get("company") or {},
            company_dna=state.get("company_dna") or config.get("company_dna") or {},
            opportunities=_flatten_opportunities(state.get("content_opportunities") or {}),
            business_goals=state.get("business_goals") or config.get("business_goals") or [],
        )
        state.setdefault("logs", []).append("Content strategy generated.")
        return state
    except Exception as exc:
        logger.exception("Content strategy generation failed")
        state["error"] = f"Content strategy generation failed: {exc}"
        return state
