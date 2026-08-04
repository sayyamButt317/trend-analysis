import logging
from typing import Any

from agents.competitor.state.competitor_state import CompetitorState
from agents.trend.services.competitor_discovery import discover_competitors
from agents.trend.services.competitor_matcher import DEFAULT_COMPETITOR_TARGET
from agents.trend.services.manual_competitors import resolve_manual_competitors

logger = logging.getLogger(__name__)

Competitor = dict[str, Any]
Company = dict[str, Any]

DISCOVERY_POOL_MULTIPLIER = 4


def _manual_competitor_inputs(config: dict, filters: dict) -> list[str]:
    return filters.get("competitors") or config.get("competitors") or []


async def find_competitors(
    company: Company,
    filters: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> tuple[list[Competitor], dict[str, Any], str | None]:
    config = config or {}
    company_name = (company.get("name") or config.get("company_name") or "").strip()
    manual_inputs = _manual_competitor_inputs(config, filters)
    manual_mode = bool(manual_inputs)
    competitor_limit = int(
        filters.get("competitor_limit") or config.get("competitor_limit") or DEFAULT_COMPETITOR_TARGET
    )
    region = filters.get("region") or config.get("region")

    if not company_name and not manual_mode:
        return [], {}, "Company name is required for competitor analysis."

    if not company_name:
        company_name = "Your company"

    if manual_mode:
        candidates, resolve_warnings = await resolve_manual_competitors(
            manual_inputs,
            region=region,
        )
        filters_applied = {
            "region": region,
            "competitors": manual_inputs,
            "competitor_limit": competitor_limit,
            "matching_mode": "manual",
            "discovery_warnings": resolve_warnings,
        }
        if not candidates:
            return (
                [],
                filters_applied,
                "No valid competitor Instagram accounts could be resolved from the names provided.",
            )
        return candidates[:competitor_limit], filters_applied, None

    pool_multiplier = int(
        (config.get("runtime_profile") or {}).get("discovery_candidate_multiplier") or DISCOVERY_POOL_MULTIPLIER
    )
    pool_size = competitor_limit * pool_multiplier
    if not (config.get("runtime_profile") or {}).get("serverless"):
        pool_size = max(pool_size, 120)
    try:
        candidates, filters_applied = await discover_competitors(
            company_name=company_name,
            industry=filters.get("industry") or config.get("industry"),
            category=filters.get("category") or config.get("category"),
            region=region,
            country=filters.get("country") or config.get("country"),
            city=filters.get("city") or config.get("city"),
            keywords=filters.get("keywords") or config.get("keywords") or [],
            company_description=company.get("description") or config.get("company_description"),
            company_profile=company.get("profile") or config.get("company_profile"),
            company_signals=company.get("company_signals") or config.get("company_signals"),
            company_username=company.get("instagram_username") or config.get("company_username"),
            company_website=company.get("website") or config.get("company_website"),
            exclude_usernames=filters.get("exclude_usernames") or config.get("exclude_usernames") or [],
            limit=competitor_limit,
            pool_size=pool_size,
        )
    except Exception:
        logger.exception("Failed to discover competitors for company=%s", company_name)
        return [], {}, "Competitor discovery failed due to an internal error. Check server logs."

    if not candidates:
        return [], filters_applied, f"No competitor accounts found for {company_name}."

    filters_applied["matching_mode"] = "smart_competitor_search"
    filters_applied["competitor_target"] = competitor_limit
    return candidates, filters_applied, None


async def FindCompetitorNode(state: CompetitorState) -> CompetitorState:
    """Legacy fallback when intelligence pipeline did not populate competitors."""
    if state.get("error"):
        return state

    existing = state.get("verified_competitors") or state.get("discovered_influencers") or []
    if existing:
        logger.info("Skipping legacy FindCompetitor; %s verified competitor(s) already found", len(existing))
        return state

    config = state.get("config") or {}
    company = config.get("company") or {}
    filters = config.get("filters") or config

    candidates, filters_applied, error = await find_competitors(company, filters, config=config)
    if error:
        state["error"] = error
        state["discovered_influencers"] = []
        return state

    config["discovery_source"] = filters_applied.get("matching_mode") or "smart_competitor_search"
    config["filters_applied"] = filters_applied
    state["config"] = config
    state["discovered_influencers"] = candidates
    state["competitors"] = candidates
    return state
