from collections import Counter
from typing import Any
from agents.trend.services.content_analyzer import build_market_content_usage


def _normalize_media_type(post: dict) -> str:
    media_type = (post.get("media_type") or "").upper()
    product_type = (post.get("media_product_type") or "").upper()
    if product_type == "REELS" or media_type in {"REEL", "VIDEO"}:
        return "Reels"
    if media_type == "CAROUSEL_ALBUM":
        return "Carousel"
    if media_type == "IMAGE":
        return "Image"
    return media_type.title() if media_type else "Unknown"


def _simplify_post(post: dict) -> dict:
    return {
        "id": post.get("id") or post.get("media_id"),
        "caption": post.get("caption") or "",
        "media_type": _normalize_media_type(post),
        "media_url": post.get("media_url"),
        "thumbnail_url": post.get("thumbnail_url"),
        "permalink": post.get("permalink"),
        "timestamp": post.get("timestamp"),
        "likes": int(post.get("likes") or post.get("like_count") or 0),
        "comments": int(post.get("comments") or post.get("comments_count") or 0),
        "engagement_rate": float(post.get("engagement_rate") or 0),
        "hashtags": post.get("hashtags") or [],
    }


def build_competitor_response(
    *,
    company: dict[str, Any],
    filters: dict[str, Any],
    competitors: list[dict],
    processed_posts: list[dict],
    content_mix: list[dict],
    topics: list[dict],
    hashtags: list[dict],
    summary: str,
    meta: dict[str, Any],
    error: str | None = None,
    company_profile: dict[str, Any] | None = None,
    search_intelligence: dict[str, Any] | None = None,
    gap_analysis: dict[str, Any] | None = None,
    recommendations: list[dict] | None = None,
    ai_report: dict[str, Any] | None = None,
    similarity_scores: list[dict] | None = None,
) -> dict[str, Any]:
    posts_by_username: dict[str, list[dict]] = {}
    for post in processed_posts:
        username = post.get("username")
        if username:
            posts_by_username.setdefault(username, []).append(_simplify_post(post))

    competitor_profiles = []
    for item in content_mix:
        username = item.get("username")
        source = next(
            (comp for comp in competitors if comp.get("username") == username),
            {},
        )
        competitor_profiles.append(
            {
                "username": username,
                "name": source.get("name"),
                "followers": source.get("followers"),
                "profile_url": source.get("profile_url")
                or f"https://www.instagram.com/{username}/",
                "profile_picture_url": source.get("profile_picture_url"),
                "image_url": source.get("profile_picture_url"),
                "bio": source.get("bio"),
                "website": source.get("website"),
                "linkedin_url": source.get("linkedin_url"),
                "linkedin_username": source.get("linkedin_username"),
                "region_match": source.get("region_match"),
                "niche_match": source.get("niche_match"),
                "authenticity": source.get("authenticity"),
                "discovered_by": source.get("discovered_by"),
                "match_score": source.get("match_score"),
                "match_reasons": source.get("match_reasons") or [],
                "instagram_analysis": source.get("instagram_analysis"),
                "linkedin_analysis": source.get("linkedin_analysis"),
                "social_warnings": source.get("social_warnings") or [],
                "similarity": source.get("similarity"),
                "content_strategy": {
                    "post_count": item.get("post_count", 0),
                    "primary_format": item.get("primary_format"),
                    "primary_content_category": item.get("primary_content_category"),
                    "content_focus": item.get("content_focus"),
                    "media_types": item.get("media_types") or [],
                    "content_categories": item.get("content_categories") or [],
                    "themes": item.get("content_themes") or [],
                    "top_hashtags": item.get("top_hashtags") or [],
                    "avg_engagement_rate": item.get("avg_engagement_rate", 0),
                    "caption_style": item.get("caption_style") or {},
                    "best_performing_format": item.get("best_performing_format"),
                },
                "posts": posts_by_username.get(username, []),
            }
        )

    for comp in competitors:
        username = comp.get("username")
        if username and not any(item["username"] == username for item in competitor_profiles):
            competitor_profiles.append(
                {
                    "username": username,
                    "name": comp.get("name"),
                    "followers": comp.get("followers"),
                    "profile_url": comp.get("profile_url"),
                    "profile_picture_url": comp.get("profile_picture_url"),
                    "image_url": comp.get("profile_picture_url"),
                    "bio": comp.get("bio"),
                    "website": comp.get("website"),
                    "linkedin_url": comp.get("linkedin_url"),
                    "linkedin_username": comp.get("linkedin_username"),
                    "region_match": comp.get("region_match"),
                    "niche_match": comp.get("niche_match"),
                    "authenticity": comp.get("authenticity"),
                    "discovered_by": comp.get("discovered_by"),
                    "match_score": comp.get("match_score"),
                    "match_reasons": comp.get("match_reasons") or [],
                    "instagram_analysis": comp.get("instagram_analysis"),
                    "linkedin_analysis": comp.get("linkedin_analysis"),
                    "social_warnings": comp.get("social_warnings") or [],
                    "content_strategy": {
                        "post_count": 0,
                        "primary_format": None,
                        "primary_content_category": None,
                        "content_focus": None,
                        "media_types": [],
                        "content_categories": [],
                        "themes": [],
                        "top_hashtags": [],
                        "avg_engagement_rate": 0,
                        "caption_style": {},
                        "best_performing_format": None,
                    },
                    "posts": [],
                }
            )

    all_media = Counter(
        media["type"]
        for profile in competitor_profiles
        for media in profile["content_strategy"]["media_types"]
        for _ in range(media.get("count", 0))
    )
    all_themes = Counter(
        theme["theme"]
        for profile in competitor_profiles
        for theme in profile["content_strategy"]["themes"]
        for _ in range(theme.get("count", 0))
    )
    all_hashtags = Counter(
        tag for profile in competitor_profiles for tag in profile["content_strategy"]["top_hashtags"]
    )
    all_categories = Counter(
        category["category"]
        for profile in competitor_profiles
        for category in profile["content_strategy"]["content_categories"]
        for _ in range(category.get("count", 0))
    )

    post_count = len(processed_posts)
    success = not error and post_count > 0
    content_usage = build_market_content_usage(content_mix, processed_posts)

    return {
        "success": success,
        "error": error,
        "summary": summary,
        "company": {
            "name": company.get("name"),
            "instagram_username": company.get("instagram_username"),
            "website": company.get("website"),
            "services": company.get("services") or [],
            "flagship_services": company.get("flagship_services") or [],
            "extracted_signals": company.get("company_signals") or filters.get("company_signals") or {},
        },
        "filters_applied": filters,
        "matching_mode": filters.get("matching_mode") or "smart",
        "discovery_warnings": filters.get("discovery_warnings") or [],
        "competitor_intelligence": filters.get("competitor_intelligence"),
        "competitor_count": len(competitors),
        "post_count": post_count,
        "competitors": competitor_profiles,
        "market_insights": {
            "topics": topics[:10],
            "content_usage": content_usage,
            "dominant_content_types": [
                {"type": media_type, "count": count}
                for media_type, count in all_media.most_common(5)
            ],
            "dominant_content_categories": [
                {"category": category, "count": count}
                for category, count in all_categories.most_common(5)
            ],
            "dominant_themes": [
                {"theme": theme, "count": count}
                for theme, count in all_themes.most_common(5)
            ],
            "top_hashtags": [
                {"tag": tag, "count": count} for tag, count in all_hashtags.most_common(10)
            ],
            "hashtag_summary": hashtags[:10],
        },
        "meta": meta,
        "company_profile": company_profile or {},
        "search_intelligence": search_intelligence or {},
        "gap_analysis": gap_analysis or {},
        "recommendations": recommendations or [],
        "ai_report": ai_report or {},
        "similarity_scores": similarity_scores or [],
    }
