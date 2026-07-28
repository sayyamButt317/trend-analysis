from datetime import datetime, timedelta, timezone

from agents.trend.Nodes.common import parse_timestamp
from agents.trend.state.trend_state import TrendState


async def CalculateTrendScoreNode(state: TrendState) -> TrendState:
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=7)
    posts = state.get("processed_posts") or []

    recent_posts = [
        post
        for post in posts
        if (ts := parse_timestamp(post.get("timestamp"))) and ts >= recent_cutoff
    ]
    recent_by_key: dict[tuple[str, str], int] = {}
    for post in recent_posts:
        for tag in post.get("hashtags") or []:
            key = ("hashtag", str(tag).lower())
            recent_by_key[key] = recent_by_key.get(key, 0) + 1
        caption = post.get("caption") or ""
        key = ("topic", caption[:40].lower())
        recent_by_key[key] = recent_by_key.get(key, 0) + 1

    scored: list[dict] = []
    for group in state.get("trend_groups") or []:
        group_type = group.get("group_type")
        key = group.get("key")
        post_count = int(group.get("post_count") or 0)
        creator_count = int(group.get("creator_count") or 0)
        avg_engagement = float(group.get("avg_engagement_rate") or 0)
        recent_count = recent_by_key.get((group_type, str(key).lower()), 0)

        topic_growth = post_count * 2
        engagement = avg_engagement * 10
        velocity = recent_count * 5
        creators = creator_count * 3
        trend_score = round(topic_growth + engagement + velocity + creators, 2)

        scored.append(
            {
                **group,
                "topic_growth": topic_growth,
                "engagement_score": round(engagement, 2),
                "velocity_score": velocity,
                "creator_score": creators,
                "trend_score": trend_score,
            }
        )

    scored.sort(key=lambda item: item["trend_score"], reverse=True)
    state["trend_scores"] = scored
    return state
