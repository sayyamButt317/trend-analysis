import logging

from agents.competitor.pipeline_log import log_event
from agents.competitor.state.competitor_state import CompetitorState
from models.company import CompanyProfile
from service.Competitor.competitor_ranker import CompetitorRanker

logger = logging.getLogger(__name__)


async def SimilarityAnalysisNode(state: CompetitorState) -> CompetitorState:
    """Compute per-competitor similarity scores."""
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

    log_event("4_strategy", "Scoring similarity vs competitors", competitors=len(competitors), region=region)
    ranker = CompetitorRanker()
    ranked = ranker.rank_all(company, competitors, region=region)
    similarity_scores = [
        {
            "name": item.get("name"),
            "username": item.get("username"),
            "website": item.get("website"),
            "similarity": item.get("similarity") or {},
            "match_score": item.get("match_score"),
        }
        for item in ranked
    ]

    state["discovered_influencers"] = ranked
    state["competitors"] = ranked
    state["similarity_scores"] = similarity_scores

    ai_report = dict(state.get("ai_report") or {})
    ai_report.update(
        {
            "company": profile_data,
            "competitor_count": len(ranked),
            "similarity_scores": similarity_scores[:10],
        }
    )
    state["ai_report"] = ai_report
    top = similarity_scores[0] if similarity_scores else {}
    log_event(
        "4_strategy",
        "Similarity scores ready",
        scored=len(similarity_scores),
        top=top.get("name"),
        top_score=top.get("match_score"),
    )
    return state


