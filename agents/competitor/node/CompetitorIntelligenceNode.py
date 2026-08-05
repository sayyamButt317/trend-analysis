import logging

from agents.competitor.pipeline_log import log_event
from agents.competitor.state.competitor_state import CompetitorState
from models.company import CompanyProfile
from service.Competitor.competitor_intelligence_report import build_competitor_intelligence_report

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
        state.get("verified_competitors")
        or state.get("discovered_influencers")
        or state.get("competitors")
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

    # Enrich similarity_scores with full 9-dimension breakdown
    extended_scores = [
        {
            "name": item.get("name"),
            "username": item.get("username"),
            "website": item.get("website"),
            "similarity": item.get("similarity") or {},
            "match_score": item.get("similarity", {}).get("overall"),
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
