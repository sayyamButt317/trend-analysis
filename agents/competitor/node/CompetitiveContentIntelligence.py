"""Compare user vs competitor content usage (topics, formats, opportunities)."""

from __future__ import annotations

import logging

from agents.competitor.pipeline_log import log_event
from agents.competitor.state.competitor_state import CompetitorState
from service.Competitor.competitive_content_intelligence import build_competitive_content_intelligence

logger = logging.getLogger(__name__)


async def CompetitiveContentIntelligenceNode(state: CompetitorState) -> CompetitorState:
    if state.get("error"):
        return state

    config = state.get("config") or {}
    profile_data = dict(state.get("company_profile") or config.get("company") or {})

    content_intelligence = build_competitive_content_intelligence(
        company_profile=profile_data,
        company_analysis=state.get("company_analysis"),
        processed_posts=state.get("processed_posts") or [],
        company_posts=state.get("company_posts") or [],
        config=config,
    )

    state["content_intelligence"] = content_intelligence

    ai_report = dict(state.get("ai_report") or {})
    ai_report["content_intelligence"] = content_intelligence
    state["ai_report"] = ai_report

    log_event(
        "4_strategy",
        "Competitive content intelligence ready",
        top_topics=len(content_intelligence.get("top_topics") or []),
        top_formats=len(content_intelligence.get("top_formats") or []),
        opportunities=len(content_intelligence.get("content_opportunities") or []),
    )
    return state
