"""Propose authentic competitors via OpenAI after user Instagram + LinkedIn DNA."""

from __future__ import annotations

import logging
from typing import Any

from agents.competitor.pipeline_log import log_event
from agents.competitor.state.competitor_state import CompetitorState
from agents.trend.services.company_social_analyzer import resolve_company_social_handles
from agents.trend.services.manual_competitors import resolve_manual_competitors
from service.Competitor.competitor_proposer import MIN_COMPETITORS, CompetitorProposerService

logger = logging.getLogger(__name__)


def _manual_inputs(config: dict[str, Any], filters: dict[str, Any]) -> list[str]:
    return list(filters.get("competitors") or config.get("competitors") or [])


async def _fill_missing_socials(
    competitors: list[dict[str, Any]],
    *,
    region: str | None,
    resolve_linkedin: bool,
    max_lookups: int = 10,
) -> list[dict[str, Any]]:
    """Light Tavily fill only when OpenAI/manual left Instagram/LinkedIn blank."""
    filled: list[dict[str, Any]] = []
    lookups = 0
    for item in competitors:
        socials = dict(item.get("socials") or {})
        needs_ig = not (item.get("username") or socials.get("instagram"))
        needs_li = resolve_linkedin and not (item.get("linkedin_url") or socials.get("linkedin"))
        if (needs_ig or needs_li) and lookups < max_lookups and item.get("name"):
            try:
                handles = await resolve_company_social_handles(
                    {
                        "name": item.get("name"),
                        "website": item.get("website"),
                        "instagram_username": item.get("username") or socials.get("instagram"),
                        "linkedin_url": item.get("linkedin_url") or socials.get("linkedin"),
                        "description": item.get("description") or "",
                    },
                    region=region,
                    resolve_linkedin=needs_li,
                )
                lookups += 1
                ig = (handles.get("instagram_username") or "").strip().lstrip("@").lower() or None
                li = handles.get("linkedin_url")
                if ig:
                    item["username"] = ig
                    item["instagram_username"] = ig
                    socials["instagram"] = ig
                if li:
                    item["linkedin_url"] = li
                    socials["linkedin"] = li
                item["socials"] = socials
            except Exception:
                logger.debug("Social fill failed for %s", item.get("name"), exc_info=True)
        filled.append(item)
    return filled


async def ProposeCompetitorsNode(state: CompetitorState) -> CompetitorState:
    if state.get("error"):
        return state

    config = state.get("config") or {}
    filters = config.get("filters") or {}
    company = config.get("company") or state.get("company_profile") or {}
    company_profile = state.get("company_profile") or company
    company_analysis = state.get("company_analysis") or {}
    region = (filters.get("region") or config.get("region") or "").strip()
    competitor_limit = int(
        filters.get("competitor_limit")
        or config.get("competitor_limit")
        or MIN_COMPETITORS
    )
    filters["competitor_limit"] = competitor_limit
    config["competitor_limit"] = competitor_limit

    manual = _manual_inputs(config, filters)
    if manual:
        log_event(
            "2_discovery",
            "Using user-provided competitors (skip auto-discovery)",
            count=len(manual),
            region=region or None,
        )
        candidates, warnings = await resolve_manual_competitors(manual, region=region or None)
        resolve_linkedin = not bool(config.get("skip_linkedin"))
        candidates = await _fill_missing_socials(
            candidates,
            region=region or None,
            resolve_linkedin=resolve_linkedin,
            max_lookups=min(10, competitor_limit),
        )
        candidates = candidates[:competitor_limit]
        filters_applied = {
            **(config.get("filters_applied") or {}),
            "region": region,
            "competitors": manual,
            "competitor_limit": competitor_limit,
            "matching_mode": "manual",
            "discovery_source": "manual",
            "discovery_warnings": warnings,
        }
        config["filters_applied"] = filters_applied
        config["filters"] = filters
        config["discovery_source"] = "manual"
        state["config"] = config

        if not candidates:
            state["error"] = (
                "Could not resolve any of the provided competitors. "
                "Pass Instagram @handles, LinkedIn company URLs, or recognizable company names."
            )
            return state

        state["verified_competitors"] = candidates
        state["discovered_influencers"] = candidates
        state["competitors"] = candidates
        state.pop("error", None)
        log_event(
            "2_discovery",
            "Manual competitors ready",
            competitors=len(candidates),
            with_instagram=sum(1 for c in candidates if c.get("username")),
            with_linkedin=sum(1 for c in candidates if c.get("linkedin_url")),
        )
        return state

    if not region:
        state["error"] = "Region is required to propose authentic competitors."
        return state

    log_event(
        "2_discovery",
        "OpenAI competitor proposal starting",
        company=company.get("name"),
        region=region,
        target=competitor_limit,
    )

    try:
        proposer = CompetitorProposerService()
        competitors, meta = await proposer.propose(
            company=company,
            company_profile=company_profile,
            company_analysis=company_analysis,
            region=region,
            limit=competitor_limit,
            hints=list(company.get("competitors_hint") or company_profile.get("competitors_hint") or []),
        )
    except Exception as exc:
        logger.exception("OpenAI competitor proposal failed")
        filters_applied = {
            **(config.get("filters_applied") or {}),
            "discovery_warnings": [
                *list((config.get("filters_applied") or {}).get("discovery_warnings") or []),
                f"OpenAI competitor proposal failed ({exc}); falling back to Tavily discovery.",
            ],
        }
        config["filters_applied"] = filters_applied
        config["filters"] = filters
        state["config"] = config
        return state

    if not competitors:
        filters_applied = {
            **(config.get("filters_applied") or {}),
            "discovery_warnings": [
                *list((config.get("filters_applied") or {}).get("discovery_warnings") or []),
                "OpenAI returned no usable competitors; falling back to Tavily discovery.",
            ],
        }
        config["filters_applied"] = filters_applied
        config["filters"] = filters
        state["config"] = config
        return state

    resolve_linkedin = not bool(config.get("skip_linkedin"))
    competitors = await _fill_missing_socials(
        competitors,
        region=region,
        resolve_linkedin=resolve_linkedin,
        max_lookups=min(10, competitor_limit),
    )

    with_ig = sum(1 for c in competitors if c.get("username"))
    with_li = sum(
        1 for c in competitors if c.get("linkedin_url") or (c.get("socials") or {}).get("linkedin")
    )

    filters_applied = {
        **(config.get("filters_applied") or {}),
        **meta,
        "region": region,
        "competitor_limit": competitor_limit,
        "matching_mode": "openai_proposal",
    }
    config["filters_applied"] = filters_applied
    config["filters"] = filters
    config["discovery_source"] = "openai_competitor_proposal"
    state["config"] = config
    state["verified_competitors"] = competitors
    state["discovered_influencers"] = competitors
    state["competitors"] = competitors
    state.pop("error", None)

    log_event(
        "2_discovery",
        "OpenAI competitor proposal complete",
        competitors=len(competitors),
        with_instagram=with_ig,
        with_linkedin=with_li,
        region=region,
    )
    return state
