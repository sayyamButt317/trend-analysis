import logging
from collections import Counter
from typing import Any

from agents.competitor.pipeline_log import log_event
from agents.competitor.state.competitor_state import CompetitorState
from models.company import CompanyProfile
from service.Competitor.competitor_ranker import CompetitorRanker

logger = logging.getLogger(__name__)


def _content_gaps(
    company: CompanyProfile,
    *,
    content_mix: list[dict[str, Any]],
    competitors: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare your company content mix vs market averages."""
    company_username = (company.name or "").lower()
    market_formats: Counter[str] = Counter()
    market_themes: Counter[str] = Counter()
    market_categories: Counter[str] = Counter()

    for profile in content_mix:
        username = (profile.get("username") or "").lower()
        if username and username in company_username:
            continue
        for row in profile.get("media_types") or []:
            market_formats[row.get("type") or "Unknown"] += int(row.get("count") or 0)
        for row in profile.get("content_themes") or []:
            market_themes[row.get("theme") or "General"] += int(row.get("count") or 0)
        for row in profile.get("content_categories") or []:
            market_categories[row.get("category") or "General"] += int(row.get("count") or 0)

    competitor_services: set[str] = set()
    competitor_technologies: set[str] = set()
    for comp in competitors:
        for svc in comp.get("website_services") or []:
            if svc:
                competitor_services.add(str(svc).lower())
        intel = comp.get("website_intelligence") or {}
        for svc in intel.get("services") or []:
            competitor_services.add(str(svc).lower())
        for tech in intel.get("technologies") or []:
            competitor_technologies.add(str(tech).lower())

    company_services = {s.lower() for s in company.services if s}
    service_gaps = sorted(competitor_services - company_services)[:12]

    company_tech = {t.lower() for t in company.technologies if t}
    technology_gaps = sorted(competitor_technologies - company_tech)[:10]

    return {
        "dominant_competitor_formats": [
            {"format": fmt, "count": count} for fmt, count in market_formats.most_common(5)
        ],
        "dominant_competitor_themes": [
            {"theme": theme, "count": count} for theme, count in market_themes.most_common(8)
        ],
        "dominant_competitor_categories": [
            {"category": cat, "count": count} for cat, count in market_categories.most_common(8)
        ],
        "service_gaps": service_gaps,
        "technology_gaps": technology_gaps,
    }


async def gap_analysis_node(state: CompetitorState) -> CompetitorState:
    """Identify service, content, and positioning gaps vs competitors."""
    if state.get("error"):
        return state

    config = state.get("config") or {}
    profile_data = state.get("company_profile") or config.get("company") or {}
    company = CompanyProfile(**profile_data) if profile_data.get("name") else CompanyProfile(name="Company")

    competitors = (
        state.get("verified_competitors")
        or state.get("discovered_influencers")
        or state.get("competitors")
        or []
    )
    content_mix = state.get("content_mix") or []

    ranker = CompetitorRanker()
    base_gaps = ranker.gap_analysis(company, competitors)
    content_gaps = _content_gaps(company, content_mix=content_mix, competitors=competitors)

    merged_services = list(
        dict.fromkeys(
            [
                *(content_gaps.get("service_gaps") or []),
                *(base_gaps.get("service_gaps") or []),
            ]
        )
    )[:12]

    gaps = {
        **base_gaps,
        **content_gaps,
        "service_gaps": merged_services,
        "keyword_gaps": base_gaps.get("keyword_gaps") or [],
        "competitor_count": len(competitors),
        "content_profiles_analyzed": len(content_mix),
        "websites_analyzed": len(state.get("competitor_website_intel") or []),
        "summary": (
            f"Found {len(merged_services)} service gaps, "
            f"{len(content_gaps.get('technology_gaps') or [])} technology gaps, and "
            f"{len(content_gaps.get('dominant_competitor_themes') or [])} dominant competitor themes "
            f"across {len(competitors)} competitors."
        ),
    }

    state["gap_analysis"] = gaps
    ai_report = dict(state.get("ai_report") or {})
    ai_report["gap_analysis"] = gaps
    state["ai_report"] = ai_report

    log_event(
        "4_strategy",
        "Gap analysis complete",
        service_gaps=len(merged_services),
        tech_gaps=len(content_gaps.get("technology_gaps") or []),
        competitors=len(competitors),
    )
    return state


GapAnalysisNode = gap_analysis_node
