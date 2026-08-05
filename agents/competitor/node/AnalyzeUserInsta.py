import logging
from agents.competitor.pipeline_log import log_event
from agents.competitor.node.user_social_utils import (
    apply_user_instagram_insights,
    enrich_company_profile_for_discovery,
    merge_company_analysis,
)
from agents.competitor.state.competitor_state import CompetitorState
from agents.trend.services.instagramuser_details import InstagramRateLimitError
from service.AnalyzeUserInstagram.contentstrategy import analyze_user_instagram



logger = logging.getLogger(__name__)


async def AnalyzeUserInstaNode(state: CompetitorState) -> CompetitorState:
    config = state.get("config") or {}
    filters = config.get("filters") or config
    company = dict(config.get("company") or {})
    post_limit = int(filters.get("post_limit") or config.get("post_limit") or 10)

    username = (
        config.get("company_instagram_username")
        or company.get("instagram_username")
        or ""
    ).strip().lstrip("@").lower()

    if not username:
        log_event("1_user_profile", "User Instagram skipped — no username provided")
        merge_company_analysis(state, {"user_instagram": {"skipped": True, "reason": "not_provided"}})
        enrich_company_profile_for_discovery(state)
        return state

    company["instagram_username"] = username
    config["company"] = company

    log_event("1_user_profile", "Fetching user Instagram profile & posts", username=f"@{username}", post_limit=post_limit)
    try:
        result = await analyze_user_instagram(company, post_limit=post_limit)
    except InstagramRateLimitError:
        log_event("1_user_profile", "User Instagram rate limited — continuing pipeline", username=f"@{username}")
        merge_company_analysis(
            state,
            {
                "user_instagram": {
                    "skipped": False,
                    "username": username,
                    "warnings": ["Instagram API rate limit reached while analyzing your profile."],
                }
            },
        )
        enrich_company_profile_for_discovery(state)
        return state

    if result.get("skipped") or not result.get("profile"):
        merge_company_analysis(state, {"user_instagram": result})
        state["config"] = config
        return state



    profile = result["profile"]
    analysis = result["instagram"] or {}
    posts = result.get("posts") or []
    config = apply_user_instagram_insights(
        config,
        username=username,
        profile=profile,
        analysis=analysis,
    )
    state["config"] = config
    state["company_posts"] = posts

    merge_company_analysis(
        state,
        {
            "user_instagram": result,
            "instagram": analysis,
            "instagram_posts": posts,
            "social_handles": {
                **((state.get("company_analysis") or {}).get("social_handles") or {}),
                **(result.get("social_handles") or {}),
            },
            "detected_niche": analysis.get("detected_niche") or result.get("detected_niche"),
            "detected_category": analysis.get("primary_content_category"),
        },
    )
    enrich_company_profile_for_discovery(state)

    log_event(
        "1_user_profile",
        "User Instagram analyzed",
        username=f"@{username}",
        niche=analysis.get("detected_niche"),
        posts=len(posts),
    )
    return state


