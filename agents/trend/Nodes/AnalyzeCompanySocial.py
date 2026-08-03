import logging

from agents.trend.services.company_social_analyzer import analyze_company_social_presence
from agents.trend.state.trend_state import TrendState

logger = logging.getLogger(__name__)


async def AnalyzeCompanySocialNode(state: TrendState) -> TrendState:
    config = state.get("config") or {}
    if config.get("agent_mode") != "company_trend":
        return state

    company = config.get("company") or {}
    filters = config.get("filters") or {}
    region = config.get("region") or filters.get("region")
    post_limit = int(filters.get("post_limit") or config.get("post_limit") or 15)

    analysis = await analyze_company_social_presence(
        company,
        region=region,
        post_limit=post_limit,
    )

    handles = analysis.get("social_handles") or {}
    company = {
        **company,
        "instagram_username": handles.get("instagram_username") or company.get("instagram_username"),
        "instagram_url": handles.get("instagram_url") or company.get("instagram_url"),
        "linkedin_url": handles.get("linkedin_url") or company.get("linkedin_url"),
        "linkedin_username": handles.get("linkedin_username") or company.get("linkedin_username"),
    }

    if analysis.get("detected_category"):
        config["detected_category"] = analysis["detected_category"]
        config["category"] = analysis["detected_category"]
        filters["industry"] = filters.get("industry") or analysis["detected_category"]

    config["company"] = company
    config["company_username"] = company.get("instagram_username")
    config["filters"] = filters
    state["config"] = config
    state["company_analysis"] = analysis
    state["company_posts"] = analysis.get("instagram_posts") or []
    state["linkedin_posts"] = analysis.get("linkedin_posts") or []
    state["pain_points"] = analysis.get("pain_points") or []

    logger.info(
        "Company social analysis: IG=@%s LinkedIn=%s posts=%s/%s pain_points=%s",
        handles.get("instagram_username") or "none",
        handles.get("linkedin_url") or "none",
        len(analysis.get("instagram_posts") or []),
        len(analysis.get("linkedin_posts") or []),
        len(analysis.get("pain_points") or []),
    )
    return state
