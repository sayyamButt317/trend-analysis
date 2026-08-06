import logging

from agents.competitor.pipeline_log import log_event
from agents.competitor.state.competitor_state import CompetitorState
from models.company import CompanyProfile
from service.Competitor.competitor_intelligence_report import (
    _competitor_lookup_key,
    _user_entity,
    build_competitor_intelligence_report,
    compute_competitor_similarity,
    similarity_to_percentages,
)

logger = logging.getLogger(__name__)


async def competitor_intelligence_node(state: CompetitorState) -> CompetitorState:
    """Build full user-vs-competitor intelligence report."""
    if state.get("error"):
        return state

    config = state.get("config") or {}
    filters = config.get("filters") or config
    region = filters.get("region") or config.get("region")
    profile_data = state.get("company_profile") or config.get("company") or {}
    company = CompanyProfile(**profile_data) if profile_data.get("name") else CompanyProfile(name="Company")

    competitors = (
        state.get("discovered_influencers")
        or state.get("competitors")
        or state.get("verified_competitors")
        or []
    )

    log_event(
        "4_strategy",
        "Building competitor intelligence report (similarity, gaps, signals, reviews, SWOT)",
        competitors=len(competitors),
    )
    report = build_competitor_intelligence_report(
        company=company,
        competitors=competitors,
        company_analysis=state.get("company_analysis"),
        company_profile=profile_data,
        gap_analysis=state.get("gap_analysis"),
        region=region,
    )

    state["competitor_intelligence_report"] = report

    score_lookup = {
        _competitor_lookup_key(item): item
        for item in report.get("similarity_vs_competitors") or []
        if _competitor_lookup_key(item)
    }
    enriched_competitors = []
    for comp in competitors:
        matched = score_lookup.get(_competitor_lookup_key(comp))
        if matched:
            similarity = matched.get("similarity") or {}
            enriched_competitors.append(
                {
                    **comp,
                    "similarity": similarity,
                    "similarity_percentages": matched.get("similarity_percentages")
                    or similarity_to_percentages(similarity),
                    "match_score": matched.get("match_score") or similarity.get("overall"),
                }
            )
        else:
            enriched_competitors.append(comp)
    state["discovered_influencers"] = enriched_competitors
    state["competitors"] = enriched_competitors

    extended_scores = [
        {
            "name": item.get("name"),
            "username": item.get("username"),
            "website": item.get("website"),
            "similarity": item.get("similarity") or {},
            "similarity_percentages": item.get("similarity_percentages")
            or similarity_to_percentages(item.get("similarity") or {}),
            "match_score": item.get("match_score") or item.get("similarity", {}).get("overall"),
        }
        for item in report.get("similarity_vs_competitors") or []
    ]
    if extended_scores:
        state["similarity_scores"] = extended_scores

    ai_report = dict(state.get("ai_report") or {})
    ai_report["competitor_intelligence_report"] = report
    ai_report["average_similarity"] = report.get("average_similarity")
    ai_report["competitor_gaps"] = report.get("gaps")
    state["ai_report"] = ai_report

    avg = report.get("average_similarity") or {}
    log_event(
        "4_strategy",
        "Intelligence report ready",
        competitors=len(competitors),
        avg_similarity=avg.get("overall"),
        gaps=len((report.get("gaps") or {}).get("services") or []),
    )
    return state


CompetitorIntelligenceNode = competitor_intelligence_node
