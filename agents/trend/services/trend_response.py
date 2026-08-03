from typing import Any
from agents.trend.services.content_analyzer import build_market_content_usage


def _reels_share(profile: dict[str, Any]) -> float:
    for item in profile.get("media_types") or []:
        if item.get("type") == "Reels":
            return float(item.get("share_pct") or 0)
    return 0.0


def _reels_engagement(posts: list[dict]) -> float:
    reel_posts = [
        post
        for post in posts
        if (post.get("media_type") or post.get("normalized_media_type") or "").lower()
        in {"reels", "reel", "video"}
        or (post.get("media_product_type") or "").upper() == "REELS"
    ]
    if not reel_posts:
        return 0.0
    return round(
        sum(float(post.get("engagement_rate") or 0) for post in reel_posts) / len(reel_posts),
        4,
    )


def build_competitor_strategies(
    content_mix: list[dict[str, Any]],
    processed_posts: list[dict[str, Any]],
) -> dict[str, Any]:
    posts_by_user: dict[str, list[dict]] = {}
    for post in processed_posts:
        username = post.get("username")
        if username:
            posts_by_user.setdefault(username, []).append(post)

    strategies: list[dict[str, Any]] = []
    for profile in content_mix:
        username = profile.get("username")
        user_posts = posts_by_user.get(username or "", [])
        strategies.append(
            {
                "username": username,
                "post_count": profile.get("post_count") or 0,
                "primary_format": profile.get("primary_format"),
                "primary_content_category": profile.get("primary_content_category"),
                "content_focus": profile.get("content_focus"),
                "avg_engagement_rate": profile.get("avg_engagement_rate"),
                "media_types": profile.get("media_types") or [],
                "content_categories": profile.get("content_categories") or [],
                "top_hashtags": profile.get("top_hashtags") or [],
                "caption_style": profile.get("caption_style") or {},
                "posting_frequency": profile.get("posting_frequency") or {},
                "best_performing_format": profile.get("best_performing_format"),
                "reels_share_pct": _reels_share(profile),
                "reels_avg_engagement_rate": _reels_engagement(user_posts),
            }
        )

    strategies.sort(
        key=lambda item: (
            item.get("reels_share_pct") or 0,
            item.get("reels_avg_engagement_rate") or 0,
            item.get("avg_engagement_rate") or 0,
        ),
        reverse=True,
    )

    reels_leader = strategies[0] if strategies else None
    engagement_leader = max(
        strategies,
        key=lambda item: float(item.get("avg_engagement_rate") or 0),
        default=None,
    )
    posting_leader = max(
        strategies,
        key=lambda item: float((item.get("posting_frequency") or {}).get("posts_per_week") or 0),
        default=None,
    )

    return {
        "competitors": strategies,
        "reels_leader": {
            "username": reels_leader.get("username"),
            "reels_share_pct": reels_leader.get("reels_share_pct"),
            "reels_avg_engagement_rate": reels_leader.get("reels_avg_engagement_rate"),
            "content_focus": reels_leader.get("content_focus"),
        }
        if reels_leader
        else None,
        "engagement_leader": {
            "username": engagement_leader.get("username"),
            "avg_engagement_rate": engagement_leader.get("avg_engagement_rate"),
        }
        if engagement_leader
        else None,
        "posting_frequency_leader": {
            "username": posting_leader.get("username"),
            "posts_per_week": (posting_leader.get("posting_frequency") or {}).get(
                "posts_per_week"
            ),
        }
        if posting_leader
        else None,
    }


def build_trend_response(
    *,
    company: dict[str, Any],
    config: dict[str, Any],
    processed_posts: list[dict[str, Any]],
    hashtags: list[dict[str, Any]],
    topics: list[dict[str, Any]],
    trend_scores: list[dict[str, Any]],
    viral_posts: list[dict[str, Any]],
    viral_sounds: list[dict[str, Any]],
    viral_categories: list[dict[str, Any]],
    content_mix: list[dict[str, Any]],
    discovered_influencers: list[dict[str, Any]],
    trend_summary: str,
    meta: dict[str, Any],
    web_trends: dict[str, Any] | None = None,
    web_crawl: dict[str, Any] | None = None,
    company_analysis: dict[str, Any] | None = None,
    company_posts: list[dict[str, Any]] | None = None,
    linkedin_posts: list[dict[str, Any]] | None = None,
    pain_points: list[dict[str, Any]] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    web_trends = web_trends or {}
    company_analysis = company_analysis or {}
    competitor_insights = build_competitor_strategies(content_mix, processed_posts)
    market_insights = build_market_content_usage(content_mix, processed_posts)

    trending_hashtags = [
        item for item in trend_scores if item.get("group_type") == "hashtag"
    ][:15]
    if not trending_hashtags:
        trending_hashtags = hashtags[:15]

    trending_topics = [
        item for item in trend_scores if item.get("group_type") == "topic"
    ][:10]
    if not trending_topics and topics:
        trending_topics = topics[:10]
    trending_reel_formats = [
        item for item in trend_scores if item.get("group_type") == "reel_format"
    ][:15]
    if not trending_reel_formats:
        trending_reel_formats = web_trends.get("reel_formats") or viral_categories 
    google_trends = web_trends.get("google_trends") or []
    google_trends_by_country = (
        web_trends.get("google_trends_by_country")
        or (web_crawl or {}).get("google_trends_by_country")
        or {}
    )
    top_queries_by_country = (
        web_trends.get("top_queries_by_country")
        or (web_crawl or {}).get("top_queries_by_country")
        or {}
    )
    rising_queries_by_country = (
        web_trends.get("rising_queries_by_country")
        or (web_crawl or {}).get("rising_queries_by_country")
        or {}
    )
    trending_reels = [
        post
        for post in viral_posts
        if post.get("is_reel")
        or (post.get("media_type") or "").lower() in {"reels", "reel", "video"}
        or (post.get("media_product_type") or "").upper() == "REELS"
    ][:20]

    post_count = len(processed_posts)
    has_web = bool(
        web_trends.get("hashtags")
        or web_trends.get("reel_formats")
        or web_trends.get("google_trends")
    )
    is_global = config.get("agent_mode") == "global_trend"
    has_company_analysis = bool(
        company_analysis.get("instagram")
        or company_posts
        or pain_points
        or company_analysis.get("detected_niche")
    )
    success = not error and (post_count > 0 or has_web or has_company_analysis)

    return {
        "success": success,
        "error": error,
        "mode": config.get("agent_mode") or ("global_trend" if is_global else "company_trend"),
        "company": {
            "name": company.get("name"),
            "detected_category": config.get("detected_category") or config.get("category"),
            "industry": config.get("industry") or (config.get("filters") or {}).get("industry"),
            "region": config.get("region") or (config.get("filters") or {}).get("region"),
            "services": company.get("services") or [],
            "flagship_services": company.get("flagship_services") or [],
            "instagram_username": company.get("instagram_username"),
            "instagram_url": company.get("instagram_url"),
            "linkedin_url": company.get("linkedin_url"),
            "linkedin_username": company.get("linkedin_username"),
        }
        if company
        else None,
        "company_analysis": company_analysis or None,
        "detected_niche": (
            company_analysis.get("detected_niche")
            or (company_analysis.get("instagram") or {}).get("detected_niche")
            or config.get("detected_niche")
        ),
        "niche_keywords": (
            (company_analysis.get("instagram") or {}).get("niche_keywords")
            or config.get("niche_keywords")
            or []
        ),
        "company_posts": company_posts or [],
        "linkedin_posts": linkedin_posts or [],
        "pain_points": pain_points or company_analysis.get("pain_points") or [],
        "instagram_insights": company_analysis.get("instagram"),
        "instagram_niche_analysis": company_analysis.get("instagram"),
        "linkedin_pain_points": pain_points or company_analysis.get("pain_points") or [],
        "audience_needs": company_analysis.get("audience_needs") or [],
        "linkedin_content_themes": company_analysis.get("linkedin_content_themes") or [],
        "analysis_warnings": company_analysis.get("warnings") or [],
        "summary": trend_summary,
        "post_count": post_count,
        "competitor_count": len(discovered_influencers),
        "discovery_source": config.get("discovery_source"),
        "web_sources": (web_crawl or {}).get("sources") or config.get("web_sources") or [],
        "source_breakdown": web_trends.get("source_breakdown") or (web_crawl or {}).get("source_breakdown") or [],
        "platform_summary": (web_crawl or {}).get("platform_summary") or {},
        "reddit_trends": (web_crawl or {}).get("reddit_trends") or {},
        "linkedin_trends": (web_crawl or {}).get("linkedin_trends") or {},
        "x_trends": (web_crawl or {}).get("x_trends") or {},
        "warnings": (web_crawl or {}).get("warnings") or [],
        "tavily_skipped": (web_crawl or {}).get("tavily_skipped"),
        "trending_hashtags": trending_hashtags,
        "trending_topics": trending_topics,
        "trending_reel_formats": trending_reel_formats,
        "google_trends": google_trends,
        "google_trends_by_country": google_trends_by_country,
        "top_queries_by_country": top_queries_by_country,
        "rising_queries_by_country": rising_queries_by_country,
        "trending_reels": trending_reels,
        "trend_scores": trend_scores[:20],
        "viral_posts": viral_posts[:20],
        "viral_sounds": viral_sounds,
        "viral_categories": viral_categories,
        "hashtags": hashtags,
        "topics": topics,
        "web_trends": web_trends,
        "market_insights": market_insights if post_count else None,
        "competitor_strategies": competitor_insights if post_count else None,
        "discovered_competitors": discovered_influencers,
        "meta": meta,
    }
