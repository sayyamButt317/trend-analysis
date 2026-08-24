from __future__ import annotations
import logging
from collections import defaultdict
from typing import Any
from datetime import datetime
from agents.contentrecommendation.state.contentstate import ContentState

logger = logging.getLogger(__name__)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_platform(platform: str) -> str:
    return platform.strip().lower().replace("-", "_").replace(" ", "_")


def _get_posts(data: dict[str, Any]) -> list[dict[str, Any]]:
    posts = (
        data.get("posts")
        or data.get("content")
        or data.get("items")
        or []
    )

    if not isinstance(posts, list):
        return []

    return [
        post
        for post in posts
        if isinstance(post, dict)
    ]


def _post_engagement_rate(post: dict[str, Any]) -> float:
    """
    Returns engagement rate for one post.

    Priority:
    1. Existing engagement_rate
    2. Existing engagementRate
    3. Calculate from likes + comments + shares / followers
    """

    existing = (
        post.get("engagement_rate")
        or post.get("engagementRate")
    )

    if existing is not None:
        return _safe_float(existing)

    likes = _safe_int(
        post.get("likes")
        or post.get("like_count")
        or post.get("likes_count")
    )

    comments = _safe_int(
        post.get("comments")
        or post.get("comment_count")
        or post.get("comments_count")
    )

    shares = _safe_int(
        post.get("shares")
        or post.get("share_count")
        or post.get("shares_count")
    )

    followers = _safe_int(
        post.get("followers")
        or post.get("followers_count")
    )

    if followers <= 0:
        return 0.0

    engagement = likes + comments + shares

    return (engagement / followers) * 100


def _get_format(post: dict[str, Any]) -> str | None:
    value = (
        post.get("format")
        or post.get("media_type")
        or post.get("normalized_media_type")
        or post.get("content_type")
    )

    if not value:
        return None

    return str(value).strip().lower()


def _get_topics(post: dict[str, Any]) -> list[str]:
    topics = (
        post.get("topics")
        or post.get("topic")
        or post.get("content_topics")
        or []
    )

    if isinstance(topics, str):
        return [topics.strip()] if topics.strip() else []

    if not isinstance(topics, list):
        return []

    return [
        str(topic).strip()
        for topic in topics
        if str(topic).strip()
    ]


def _calculate_average_engagement(posts: list[dict[str, Any]]) -> float:
    if not posts:
        return 0.0

    rates = [
        _post_engagement_rate(post)
        for post in posts
    ]

    rates = [rate for rate in rates if rate > 0]

    if not rates:
        return 0.0

    return round(sum(rates) / len(rates), 2)


def _calculate_best_formats(
    posts: list[dict[str, Any]],
    limit: int = 5,
) -> list[dict[str, Any]]:

    format_rates: dict[str, list[float]] = defaultdict(list)

    for post in posts:
        content_format = _get_format(post)

        if not content_format:
            continue

        rate = _post_engagement_rate(post)

        if rate > 0:
            format_rates[content_format].append(rate)

    results = []

    for content_format, rates in format_rates.items():
        if not rates:
            continue

        results.append(
            {
                "format": content_format,
                "engagement_rate": round(
                    sum(rates) / len(rates),
                    2,
                ),
                "post_count": len(rates),
            }
        )

    results.sort(
        key=lambda item: item["engagement_rate"],
        reverse=True,
    )

    return results[:limit]


def _calculate_best_topics(
    posts: list[dict[str, Any]],
    limit: int = 10,
) -> list[dict[str, Any]]:

    topic_rates: dict[str, list[float]] = defaultdict(list)

    for post in posts:
        topics = _get_topics(post)

        if not topics:
            continue

        rate = _post_engagement_rate(post)

        if rate <= 0:
            continue

        for topic in topics:
            topic_rates[topic].append(rate)

    results = []

    for topic, rates in topic_rates.items():
        if not rates:
            continue

        results.append(
            {
                "topic": topic,
                "engagement_rate": round(
                    sum(rates) / len(rates),
                    2,
                ),
                "post_count": len(rates),
            }
        )

    results.sort(
        key=lambda item: item["engagement_rate"],
        reverse=True,
    )

    return results[:limit]


def _get_best_posts(
    posts: list[dict[str, Any]],
    limit: int = 5,
) -> list[dict[str, Any]]:

    ranked = []

    for post in posts:
        rate = _post_engagement_rate(post)

        if rate <= 0:
            continue

        ranked.append(
            {
                **post,
                "_calculated_engagement_rate": rate,
            }
        )

    ranked.sort(
        key=lambda post: post["_calculated_engagement_rate"],
        reverse=True,
    )

    results = []

    for post in ranked[:limit]:

        results.append(
            {
                "id": post.get("id"),
                "url": (
                    post.get("url")
                    or post.get("permalink")
                    or post.get("post_url")
                ),
                "caption": (
                    post.get("caption")
                    or post.get("text")
                    or ""
                )[:300],
                "format": _get_format(post),
                "topics": _get_topics(post),
                "engagement_rate": round(
                    post["_calculated_engagement_rate"],
                    2,
                ),
                "likes": _safe_int(
                    post.get("likes")
                    or post.get("like_count")
                    or post.get("likes_count")
                ),
                "comments": _safe_int(
                    post.get("comments")
                    or post.get("comment_count")
                    or post.get("comments_count")
                ),
                "shares": _safe_int(
                    post.get("shares")
                    or post.get("share_count")
                    or post.get("shares_count")
                ),
            }
        )

    return results


def _calculate_posting_frequency(
    posts: list[dict[str, Any]],
) -> float | None:
    """
    Approximate posts per week based on post dates.

    Requires posts to contain a recognizable date field.
    """

    if len(posts) < 2:
        return None

    dates = []

    for post in posts:
        date = (
            post.get("created_at")
            or post.get("published_at")
            or post.get("timestamp")
            or post.get("date")
        )

        if not date:
            continue

        dates.append(str(date))

    if len(dates) < 2:
        return None

    try:
        parsed_dates = []
        for value in dates:
            value = value.replace("Z", "+00:00")
            parsed_dates.append(
                datetime.fromisoformat(value)
            )
        parsed_dates.sort()
        first = parsed_dates[0]
        last = parsed_dates[-1]
        days = (last - first).total_seconds() / 86400
        if days <= 0:
            return None
        weeks = days / 7
        if weeks <= 0:
            return None
        return round(len(posts) / weeks, 2)
    except Exception:
        return None


def analyze_social_performance(
    social_media_platform: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    platform = _normalize_platform(
        social_media_platform
    )
    posts = _get_posts(data)
    result = {
        "platform": platform,
        "average_engagement_rate": _calculate_average_engagement(posts),
        "best_formats": _calculate_best_formats(posts),
        "best_topics": _calculate_best_topics(posts),
        "best_posts": _get_best_posts(posts),
        "posting_frequency": _calculate_posting_frequency(posts),
        "post_count": len(posts),
    }
    return result


async def AnalyzeSocialPerformanceNode(
    state: ContentState,
) -> ContentState:
    try:
        company_analysis = (
            state.get("company_analysis")
            or {}
        )
        competitor_analysis = (
            state.get("competitor_analysis")
            or {}
        )
        performance = {}
        # --------------------------------------------------
        # Instagram
        # --------------------------------------------------
        instagram_data = (
            company_analysis.get("instagram")
            or company_analysis.get("user_instagram")
            or {}
        )
        instagram_posts = (
            company_analysis.get("instagram_posts")
            or []
        )
        if instagram_posts:
            instagram_data = {
                **instagram_data,
                "posts": instagram_posts,
            }
        if instagram_data:
            performance["instagram"] = analyze_social_performance(
                "instagram",
                instagram_data,
            )
        # --------------------------------------------------
        # LinkedIn
        # --------------------------------------------------
        linkedin_data = (
            company_analysis.get("linkedin")
            or company_analysis.get("user_linkedin")
            or {}
        )
        linkedin_posts = (
            company_analysis.get("linkedin_posts")
            or []
        )
        if linkedin_posts:
            linkedin_data = {
                **linkedin_data,
                "posts": linkedin_posts,
            }
        if linkedin_data:
            performance["linkedin"] = analyze_social_performance(
                "linkedin",
                linkedin_data,
            )
        # --------------------------------------------------
        # Competitor comparison
        # --------------------------------------------------
        competitor_social = (
            competitor_analysis.get("social_performance")
            or {}
        )
        performance["competitor_comparison"] = (
            competitor_social
        )
        # --------------------------------------------------
        # Save output
        # --------------------------------------------------
        state["social_performance"] = performance
        state.setdefault("logs", []).append(
            "Social media performance analysis completed."
        )
        return state

    except Exception as exc:
        logger.exception(
            "Social performance analysis failed"
        )
        state["error"] = (
            f"Social performance analysis failed: {str(exc)}"
        )

        return state