import logging
from copy import deepcopy
from agents.analyzecompany.pipeline_log import log_event
from agents.analyzecompany.node.user_social_utils import (
    apply_user_instagram_insights,
    enrich_company_profile_for_discovery,
    merge_company_analysis,
)
from agents.analyzecompany.state.companystate import AnalyzeCompanyState
from agents.trend.services.instagramuser_details import InstagramRateLimitError
from service.AnalyzeUserInstagram.contentstrategy import analyze_user_instagram

logger = logging.getLogger(__name__)


async def AnalyzeUserInstaNode(state: AnalyzeCompanyState) -> AnalyzeCompanyState:

    config = state.get("config") or {}
    filters = config.get("filters") or config
    company = dict(config.get("company") or {})

    post_limit = int(
        filters.get("post_limit")
        or config.get("post_limit")
        or 10
    )

    username = (
        config.get("company_instagram_username")
        or company.get("instagram_username")
        or ""
    ).strip().lstrip("@").lower()

    if not username:
        log_event(
            "1_company",
            "User Instagram skipped",
            reason="username not provided",
        )

        merge_company_analysis(
            state,
            {
                "user_instagram": {
                    "skipped": True,
                    "reason": "not_provided",
                }
            },
        )

        enrich_company_profile_for_discovery(state)
        return state

    company["instagram_username"] = username
    config["company"] = company
    log_event(
        "1_company",
        "Fetching Instagram profile",
        username=f"@{username}",
        posts=post_limit,
    )

    try:
        result = await analyze_user_instagram(
            company,
            post_limit=post_limit,
        )
    except InstagramRateLimitError:
        warning = "Instagram API rate limit reached."
        merge_company_analysis(
            state,
            {
                "user_instagram": {
                    "username": username,
                    "warnings": [warning],
                }
            },
        )

        state.setdefault("warnings", []).append(warning)
        enrich_company_profile_for_discovery(state)
        return state
    if result.get("skipped") or not result.get("profile"):
        merge_company_analysis(
            state,
            {
                "user_instagram": result,
            },
        )

        state["user_instagram"] = result
        state["config"] = config

        return state

    profile = result["profile"]
    analysis = result.get("instagram") or {}
    posts = result.get("posts") or []
    config = apply_user_instagram_insights(
        config=config,
        username=username,
        profile=profile,
        analysis=analysis,
    )

    signals = deepcopy(config.get("company_signals") or {})

    signals.update(
        {
            "instagram_username": username,
            "instagram_name": profile.get("name"),
            "bio": profile.get("biography"),
            "website": profile.get("website"),
            "followers": profile.get("followers_count"),
            "following": profile.get("follows_count"),
            "media_count": profile.get("media_count"),
            "avg_engagement_rate": analysis.get("avg_engagement_rate"),
            "primary_format": analysis.get("primary_format"),
            "content_categories": analysis.get("content_categories"),
            "content_themes": analysis.get("content_themes"),
            "hashtags": analysis.get("top_hashtags"),
            "posting_frequency": analysis.get("posting_frequency"),
        }
    )

    config["company_signals"] = signals

    state["config"] = config

    state["company_posts"] = posts

    state["user_instagram"] = result
    state["user_instagram_profile"] = profile
    state["user_instagram_analysis"] = analysis

    merge_company_analysis(
        state,
        {
            "user_instagram": result,
            "instagram": analysis,
            "instagram_posts": posts,
            "social_handles": {
                **(
                    (state.get("company_analysis") or {})
                    .get("social_handles")
                    or {}
                ),
                **(result.get("social_handles") or {}),
            },
        },
    )

    # Content signals only — do not treat IG niche/services as company DNA.
    state["discovery_features"] = {
        **(state.get("discovery_features") or {}),
        "instagram_hashtags": analysis.get("top_hashtags") or [],
        "instagram_content_categories": analysis.get("content_categories") or [],
        "instagram_content_themes": analysis.get("content_themes") or [],
        "instagram_target_audience_hints": analysis.get("target_audience") or [],
    }

    state["instagram_competitor_hints"] = {
        "mentions": analysis.get("top_mentions") or [],
        "brand_collaborations": analysis.get("brand_collaborations") or [],
        "frequent_tags": analysis.get("frequent_tags") or [],
    }

    enrich_company_profile_for_discovery(state)

    log_event(
        "1_company",
        "Instagram analysis complete",
        username=f"@{username}",
        followers=profile.get("followers_count"),
        posts=len(posts),
        themes=len(analysis.get("content_themes") or []),
    )

    from agents.analyzecompany.routing import mark_platform_coverage

    return mark_platform_coverage(state, source="instagram")