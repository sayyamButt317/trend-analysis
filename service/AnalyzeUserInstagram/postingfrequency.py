from typing import Any

from agents.trend.Nodes.common import parse_timestamp


def analyze_posting_frequency(posts: list[dict[str, Any]]) -> dict[str, Any]:
    timestamps = [
        parse_timestamp(post.get("timestamp"))
        for post in posts
        if post.get("timestamp")
    ]
    timestamps = [ts for ts in timestamps if ts]
    timestamps.sort()

    if len(timestamps) < 2:
        return {
            "post_count": len(posts),
            "date_range_days": 0,
            "avg_days_between_posts": None,
            "posts_per_week": None,
        }

    gaps = [(timestamps[i + 1] - timestamps[i]).days for i in range(len(timestamps) - 1)]
    span_days = max((timestamps[-1] - timestamps[0]).days, 1)
    return {
        "post_count": len(posts),
        "date_range_days": span_days,
        "avg_days_between_posts": round(sum(gaps) / len(gaps), 1) if gaps else None,
        "posts_per_week": round(len(posts) / max(span_days / 7, 1), 1),
    }
