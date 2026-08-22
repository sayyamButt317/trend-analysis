"""Hydrate competitor state from analyze-company handoff fields."""

from __future__ import annotations

from typing import Any

from agents.competitor.pipeline_log import log_event
from agents.competitor.state.competitor_state import CompetitorState

_INTELLIGENCE_KEYS = (
    "executive_snapshot",
    "digital_presence",
    "market_position",
    "positioning_analysis",
    "strengths_and_weaknesses",
    "growth_opportunities",
    "recommended_actions",
)


def has_prebuilt_company_context(config: dict[str, Any] | None) -> bool:
    """True when analyze-company output was passed and in-pipeline re-analysis can be skipped."""
    if not config or not config.get("skip_company_analysis"):
        return False
    company = config.get("company") or {}
    if not isinstance(company, dict):
        return False
    has_identity = bool(company.get("name") or company.get("website"))
    has_dna = bool(
        company.get("services")
        or company.get("flagship_services")
        or config.get("summary_text")
        or config.get("company_analysis")
    )
    return has_identity and has_dna


def _derive_company_signals(config: dict[str, Any], company_analysis: dict[str, Any]) -> dict[str, Any]:
    signals = dict(config.get("company_signals") or {})
    analysis = company_analysis or {}
    ig = analysis.get("instagram") or {}
    if ig:
        signals.setdefault("instagram_analyzed", True)
        if ig.get("followers") is not None:
            signals["instagram_followers"] = ig.get("followers")
        if ig.get("avg_engagement_rate") is not None:
            signals["instagram_engagement_rate"] = ig.get("avg_engagement_rate")
    if analysis.get("is_hiring") is not None:
        signals["is_hiring"] = analysis.get("is_hiring")
    if analysis.get("company_size"):
        signals["company_size"] = analysis.get("company_size")
    if analysis.get("linkedin_content_themes"):
        signals["linkedin_content_themes"] = analysis.get("linkedin_content_themes")
    return signals


async def HydrateCompanyContextNode(state: CompetitorState) -> CompetitorState:
    config = dict(state.get("config") or {})

    if not has_prebuilt_company_context(config):
        config["skip_company_analysis"] = False
        state["config"] = config
        log_event("1_user_profile", "No analyze-company handoff — will analyze company in-pipeline")
        return state

    company = dict(config.get("company") or {})
    base_company = dict(config.get("company") or {})
    for key in ("instagram_username", "instagram_url", "linkedin_url", "website", "name", "region"):
        if not company.get(key) and base_company.get(key):
            company[key] = base_company[key]

    summary_text = (config.get("summary_text") or "").strip()
    if summary_text:
        company["profile"] = summary_text
        company["description"] = summary_text
        company["company_summary_text"] = summary_text
        config["company_description"] = summary_text
        config["company_profile"] = summary_text

    company_analysis = dict(config.get("company_analysis") or {})
    config["company"] = {**(config.get("company") or {}), **company}
    config["company_name"] = config.get("company_name") or company.get("name")
    config["company_instagram_username"] = (
        config.get("company_instagram_username") or company.get("instagram_username")
    )
    config["company_linkedin_url"] = config.get("company_linkedin_url") or company.get("linkedin_url")
    config["company_website"] = config.get("company_website") or company.get("website")
    config["company_signals"] = _derive_company_signals(config, company_analysis)
    config["skip_company_analysis"] = True
    config["company_analysis_source"] = "analyze_company"

    filters = dict(config.get("filters") or {})
    if company.get("instagram_username"):
        exclude = list(filters.get("exclude_usernames") or [])
        handle = company["instagram_username"].lower().lstrip("@")
        if handle not in {item.lower().lstrip("@") for item in exclude}:
            exclude.append(handle)
        filters["exclude_usernames"] = exclude
    config["filters"] = filters

    state["config"] = config
    state["company_profile"] = company
    state["company_analysis"] = company_analysis

    for key in _INTELLIGENCE_KEYS:
        value = config.get(key)
        if value:
            state[key] = value  # type: ignore[literal-required]

    log_event(
        "1_user_profile",
        "Hydrated company context from analyze-company handoff (skip website/IG/LinkedIn re-analysis)",
        company=company.get("name"),
        has_ig=bool(company.get("instagram_username")),
        has_li=bool(company.get("linkedin_url")),
    )
    return state


def route_after_hydrate(state: CompetitorState) -> str:
    config = state.get("config") or {}
    if config.get("skip_company_analysis") and has_prebuilt_company_context(config):
        return "propose_competitors"
    return "understand_company"
