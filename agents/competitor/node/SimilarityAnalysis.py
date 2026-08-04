import logging

from agents.competitor.state.competitor_state import CompetitorState
from models.company import CompanyProfile
from service.Competitor.competitor_ranker import CompetitorRanker

logger = logging.getLogger(__name__)


async def SimilarityAnalysisNode(state: CompetitorState) -> CompetitorState:
    """Compute similarity scores, gap analysis, and recommendations."""
    if state.get("error"):
        return state

    config = state.get("config") or {}
    profile_data = state.get("company_profile") or config.get("company") or {}
    company = CompanyProfile(**profile_data)

    competitors = (
        state.get("verified_competitors")
        or state.get("discovered_influencers")
        or state.get("competitors")
        or []
    )

    ranker = CompetitorRanker()
    gaps = ranker.gap_analysis(company, competitors)
    recs = ranker.recommendations(company, gaps, competitors)
    similarity_scores = [
        {
            "name": item.get("name"),
            "username": item.get("username"),
            "website": item.get("website"),
            "similarity": item.get("similarity") or {},
            "match_score": item.get("match_score"),
        }
        for item in competitors
    ]

    state["similarity_scores"] = similarity_scores
    state["gap_analysis"] = gaps
    state["recommendations"] = recs
    state["ai_report"] = {
        "company": profile_data,
        "competitor_count": len(competitors),
        "similarity_scores": similarity_scores[:10],
        "gap_analysis": gaps,
        "recommendations": recs,
    }
    return state
