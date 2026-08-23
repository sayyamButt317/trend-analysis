from __future__ import annotations
import logging
from typing import Any
from agents.competitor.pipeline_log import log_event
from agents.competitor.state.competitor_state import CompetitorState
from service.Competitor.niche_competitive_gaps import build_niche_competitive_gaps

logger = logging.getLogger(__name__)


async def CompetitiveGapsNode(state: CompetitorState) -> CompetitorState:
    if state.get("error"):
        return state

    config = state.get("config") or {}
    profile_data = dict(state.get("company_profile") or config.get("company") or {})
    company_analysis = state.get("company_analysis") or {}

    competitors = (
        state.get("discovered_influencers")
        or state.get("competitors")
        or state.get("verified_competitors")
        or []
    )

    competitive_gaps = build_niche_competitive_gaps(
        company_profile=profile_data,
        company_analysis=company_analysis,
        competitors=competitors,
        processed_posts=state.get("processed_posts") or [],
        topics=state.get("topics") or [],
        content_mix=state.get("content_mix") or [],
        gap_analysis=state.get("gap_analysis"),
    )

    state["competitive_gaps"] = competitive_gaps

    ai_report = dict(state.get("ai_report") or {})
    ai_report["competitive_gaps"] = competitive_gaps
    state["ai_report"] = ai_report

    log_event(
        "4_strategy",
        "Niche competitive gaps ready",
        service_gaps=len(competitive_gaps.get("service_gaps") or []),
        positioning_gaps=len(competitive_gaps.get("positioning_gaps") or []),
        content_gaps=len(competitive_gaps.get("content_gaps") or []),
        technology_gaps=len(competitive_gaps.get("technology_gaps") or []),
    )
    return state
