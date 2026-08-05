import logging
from typing import Any
from agents.competitor.pipeline_log import log_event
from agents.competitor.state.competitor_state import CompetitorState
from models.company import CompanyProfile
from service.Competitor.competitor_ranker import CompetitorRanker

logger = logging.getLogger(__name__)


def _content_recommendations(gap_analysis: dict[str, Any]) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []

    themes = gap_analysis.get("dominant_competitor_themes") or []
    if themes:
        top_themes = [t.get("theme") for t in themes[:4] if t.get("theme")]
        if top_themes:
            recs.append(
                {
                    "type": "content",
                    "priority": "high",
                    "title": "Match high-performing competitor themes",
                    "detail": f"Competitors post heavily about: {', '.join(top_themes)}",
                }
            )

    formats = gap_analysis.get("dominant_competitor_formats") or []
    if formats:
        top_format = formats[0].get("format")
        if top_format:
            recs.append(
                {
                    "type": "format",
                    "priority": "medium",
                    "title": f"Increase {top_format} content",
                    "detail": f"Competitors lead with {top_format} — test more of this format in your calendar.",
                }
            )

    tech_gaps = gap_analysis.get("technology_gaps") or []
    if tech_gaps:
        recs.append(
            {
                "type": "positioning",
                "priority": "medium",
                "title": "Highlight missing technology keywords",
                "detail": f"Competitors emphasize: {', '.join(tech_gaps[:5])}",
            }
        )

    return recs


async def recommendation_node(state: CompetitorState) -> CompetitorState:

    if state.get("error"):
        return state

    config = state.get("config") or {}
    profile_data = state.get("company_profile") or config.get("company") or {}
    company = CompanyProfile(**profile_data) if profile_data.get("name") else CompanyProfile(name="Company")

    competitors = (
        state.get("discovered_influencers")
        or state.get("competitors")
        or state.get("verified_competitors")
        or []
    )
    gaps = state.get("gap_analysis") or {}
    intel_report = state.get("competitor_intelligence_report") or {}
    intel_gaps = intel_report.get("gaps") or {}

    ranker = CompetitorRanker()
    recs = ranker.recommendations(company, gaps, competitors)
    recs.extend(_content_recommendations(gaps))

    signal_gaps = intel_gaps.get("business_signals") or []
    if signal_gaps:
        top_signals = [s.get("signal") for s in signal_gaps[:4] if s.get("signal")]
        if top_signals:
            recs.append(
                {
                    "type": "signals",
                    "priority": "medium",
                    "title": "Adopt competitor business signals",
                    "detail": f"Competitors actively promote: {', '.join(top_signals)}",
                }
            )

    review_gaps = (intel_report.get("review_intelligence") or {}).get("gaps") or []
    if review_gaps:
        platforms = [g.get("platform") for g in review_gaps[:3] if g.get("platform")]
        if platforms:
            recs.append(
                {
                    "type": "reviews",
                    "priority": "high",
                    "title": "Build review presence on missing platforms",
                    "detail": f"Competitors are listed on: {', '.join(platforms)}",
                }
            )

    content_type_gaps = intel_gaps.get("content_types") or []
    if content_type_gaps:
        types = [g.get("content_type") for g in content_type_gaps[:3] if g.get("content_type")]
        if types:
            recs.append(
                {
                    "type": "content",
                    "priority": "medium",
                    "title": "Publish content types competitors use",
                    "detail": f"Consider: {', '.join(types)}",
                }
            )

    company_analysis = state.get("company_analysis") or {}
    if company_analysis.get("is_hiring"):
        recs.append(
            {
                "type": "hiring",
                "priority": "low",
                "title": "Leverage hiring momentum",
                "detail": "Your company is actively hiring — promote team/culture content competitors use to attract talent.",
            }
        )

    user_ig = (company_analysis.get("user_instagram") or {}).get("instagram") or {}
    primary_format = user_ig.get("primary_format")
    if primary_format and gaps.get("dominant_competitor_formats"):
        market_top = gaps["dominant_competitor_formats"][0].get("format")
        if market_top and market_top != primary_format:
            recs.append(
                {
                    "type": "format",
                    "priority": "high",
                    "title": "Close format gap vs market",
                    "detail": f"You focus on {primary_format}; competitors win with {market_top}.",
                }
            )

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for rec in recs:
        key = (rec.get("type"), rec.get("title"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rec)

    state["recommendations"] = deduped[:12]
    ai_report = dict(state.get("ai_report") or {})
    ai_report["recommendations"] = deduped[:12]
    ai_report["competitor_count"] = len(competitors)
    state["ai_report"] = ai_report

    log_event("4_strategy", "Recommendations generated", count=len(deduped))
    return state


RecommendationNode = recommendation_node
