from __future__ import annotations

from typing import Any, TypedDict


class ContentState(TypedDict, total=False):
    """State for the content recommendation LangGraph."""

    config: dict[str, Any]
    company: dict[str, Any]
    company_dna: dict[str, Any]
    company_analysis: dict[str, Any]
    competitor_analysis: dict[str, Any]
    content_intelligence_input: dict[str, Any]
    ninety_day_action_plan: dict[str, Any]
    business_goals: list[str]
    platforms: list[str]
    calendar_days: int

    # Node outputs
    social_performance: dict[str, Any]
    competitor_content: dict[str, Any]
    content_opportunities: dict[str, Any]
    content_strategy: dict[str, Any]
    platform_strategy: dict[str, Any]
    content_ideas: list[dict[str, Any]]
    content_calendar: dict[str, Any]

    recommendation: dict[str, Any]
    error: str | None
    logs: list[str]
