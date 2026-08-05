from collections import defaultdict
from typing import Any


def attach_engagement_rates(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for post in posts:
        item = dict(post)
        followers = max(int(item.get("followers") or item.get("followers_count") or 0), 1)
        likes = int(item.get("likes") or 0)
        comments = int(item.get("comments") or 0)
        interactions = likes + comments
        engagement_rate = round((interactions / followers) * 100, 4)
        item["interactions"] = interactions
        item["engagement_rate"] = engagement_rate
        enriched.append(item)
    return enriched


def best_performing_format(posts: list[dict[str, Any]]) -> dict[str, Any] | None:
    by_format: dict[str, list[float]] = defaultdict(list)
    for post in posts:
        fmt = post.get("normalized_media_type") or post.get("media_type") or "Unknown"
        by_format[str(fmt)].append(float(post.get("engagement_rate") or 0))

    if not by_format:
        return None

    ranked = sorted(
        (
            {
                "format": fmt,
                "avg_engagement_rate": round(sum(rates) / len(rates), 4),
                "post_count": len(rates),
            }
            for fmt, rates in by_format.items()
        ),
        key=lambda item: item["avg_engagement_rate"],
        reverse=True,
    )
    return ranked[0] if ranked else None


def analyze_engagement(posts: list[dict[str, Any]]) -> dict[str, Any]:
    if not posts:
        return {
            "avg_engagement_rate": 0.0,
            "best_performing_format": None,
            "total_interactions": 0,
        }

    posts_with_rates = attach_engagement_rates(posts)
    total_interactions = sum(int(post.get("interactions") or 0) for post in posts_with_rates)
    avg_rate = round(
        sum(float(post.get("engagement_rate") or 0) for post in posts_with_rates) / len(posts_with_rates),
        4,
    )
    return {
        "avg_engagement_rate": avg_rate,
        "best_performing_format": best_performing_format(posts_with_rates),
        "total_interactions": total_interactions,
        "posts": posts_with_rates,
    }
