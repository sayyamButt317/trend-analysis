import logging
from typing import Any

from agents.trend.services.instagramuser_details import InstagramRateLimitError
from service.AnalyzeUserInstagram.analyzecontent import (
    analyze_caption_style_summary,
    analyze_content_categories,
    analyze_media_mix,
    build_content_focus,
)
from service.AnalyzeUserInstagram.engagement import analyze_engagement
from service.AnalyzeUserInstagram.fetchprofile import (
    fetch_user_instagram_profile,
    normalize_username,
    posts_from_profile,
)
from service.AnalyzeUserInstagram.hashtags import analyze_hashtags
from service.AnalyzeUserInstagram.postingfrequency import analyze_posting_frequency

logger = logging.getLogger(__name__)


def detect_niche(
    profile: dict[str, Any],
    *,
    content_focus: str | None,
    content_categories: list[dict[str, Any]],
    primary_content_category: str | None,
) -> tuple[str | None, list[str]]:
    focus_parts = (content_focus or "").split(", ") if content_focus else []
    niche_keywords = list(
        dict.fromkeys(
            [
                *focus_parts,
                content_categories[0]["category"] if content_categories else "",
                profile.get("category") or "",
                primary_content_category or "",
            ]
        )
    )
    niche_keywords = [item for item in niche_keywords if item and item != "General Brand"]
    detected = niche_keywords[0] if niche_keywords else primary_content_category
    return detected, niche_keywords[:8]


def build_instagram_analysis(profile: dict[str, Any], posts: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a full Instagram content strategy report from profile + normalized posts."""
    engagement = analyze_engagement(posts)
    posts = engagement.pop("posts", posts)

    media_mix = analyze_media_mix(posts)
    content_categories = analyze_content_categories(posts)
    caption_style = analyze_caption_style_summary(posts)
    posting_frequency = analyze_posting_frequency(posts)
    top_hashtags = analyze_hashtags(posts)

    primary_format = media_mix[0]["type"] if media_mix else None
    primary_content_category = content_categories[0]["category"] if content_categories else None
    content_focus = build_content_focus(media_mix, content_categories)
    detected_niche, niche_keywords = detect_niche(
        profile,
        content_focus=content_focus,
        content_categories=content_categories,
        primary_content_category=primary_content_category,
    )

    bio = profile.get("biography") or profile.get("bio") or ""
    return {
        "username": profile.get("username"),
        "name": profile.get("name"),
        "bio": bio,
        "followers": profile.get("followers_count"),
        "website": profile.get("website"),
        "post_count": len(posts),
        "primary_format": primary_format,
        "primary_content_category": primary_content_category,
        "content_focus": content_focus,
        "top_hashtags": top_hashtags,
        "media_mix": media_mix,
        "content_categories": content_categories,
        "posting_frequency": posting_frequency,
        "avg_engagement_rate": engagement.get("avg_engagement_rate"),
        "best_performing_format": engagement.get("best_performing_format"),
        "total_interactions": engagement.get("total_interactions"),
        "detected_niche": detected_niche,
        "niche_keywords": niche_keywords,
        "caption_style": caption_style,
    }


async def analyze_user_instagram(
    company: dict[str, Any],
    *,
    post_limit: int = 10,
) -> dict[str, Any]:
    """Fetch and analyze the requesting company's Instagram presence."""
    username = normalize_username(
        company.get("instagram_username") or company.get("company_instagram_username")
    )
    if not username:
        return {
            "skipped": True,
            "reason": "No Instagram username provided",
            "warnings": ["Provide instagram_username to analyze your Instagram content."],
        }

    warnings: list[str] = []
    try:
        profile = await fetch_user_instagram_profile(username, post_limit=post_limit)
    except InstagramRateLimitError:
        raise
    except Exception:
        logger.exception("User Instagram fetch failed for @%s", username)
        profile = None

    if not profile:
        return {
            "skipped": False,
            "username": username,
            "warnings": [f"Could not fetch Instagram profile for @{username}."],
        }

    posts = posts_from_profile(profile, handle=username)
    for post in posts:
        post["username"] = username
        post["is_company_post"] = True

    analysis = build_instagram_analysis(profile, posts)
    return {
        "skipped": False,
        "username": username,
        "profile": profile,
        "posts": posts,
        "instagram": analysis,
        "instagram_analysis": analysis,
        "detected_niche": analysis.get("detected_niche"),
        "detected_category": analysis.get("primary_content_category"),
        "social_handles": {
            "instagram_username": username,
            "instagram_url": f"https://www.instagram.com/{username}/",
        },
        "warnings": warnings,
    }
