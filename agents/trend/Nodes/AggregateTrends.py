from collections import defaultdict

from agents.trend.Nodes.common import TOPIC_KEYWORDS
from agents.trend.state.trend_state import TrendState


def _topic_for_text(text: str) -> str:
    lowered = (text or "").lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return topic
    return "General"


async def AggregateTrendsNode(state: TrendState) -> TrendState:
    hashtag_groups: dict[str, dict] = {}
    topic_groups: dict[str, dict] = {}
    creator_groups: dict[str, dict] = {}

    for post in state.get("processed_posts") or []:
        username = post.get("username") or "unknown"
        caption = post.get("caption") or ""
        topic = _topic_for_text(
            f"{caption} {' '.join(post.get('hashtags') or [])}"
        )

        topic_entry = topic_groups.setdefault(
            topic,
            {
                "group_type": "topic",
                "key": topic,
                "post_count": 0,
                "creators": set(),
                "total_engagement_rate": 0.0,
            },
        )
        topic_entry["post_count"] += 1
        topic_entry["creators"].add(username)
        topic_entry["total_engagement_rate"] += float(post.get("engagement_rate") or 0)

        creator_entry = creator_groups.setdefault(
            username,
            {
                "group_type": "creator",
                "key": username,
                "post_count": 0,
                "total_engagement_rate": 0.0,
            },
        )
        creator_entry["post_count"] += 1
        creator_entry["total_engagement_rate"] += float(post.get("engagement_rate") or 0)

        for tag in post.get("hashtags") or []:
            normalized = str(tag).lower()
            tag_entry = hashtag_groups.setdefault(
                normalized,
                {
                    "group_type": "hashtag",
                    "key": normalized,
                    "post_count": 0,
                    "creators": set(),
                    "total_engagement_rate": 0.0,
                },
            )
            tag_entry["post_count"] += 1
            tag_entry["creators"].add(username)
            tag_entry["total_engagement_rate"] += float(post.get("engagement_rate") or 0)

    groups: list[dict] = []
    for bucket in (hashtag_groups, topic_groups, creator_groups):
        for entry in bucket.values():
            post_count = max(entry["post_count"], 1)
            groups.append(
                {
                    "group_type": entry["group_type"],
                    "key": entry["key"],
                    "post_count": entry["post_count"],
                    "creator_count": len(entry.get("creators") or {entry["key"]}),
                    "avg_engagement_rate": round(
                        entry["total_engagement_rate"] / post_count,
                        4,
                    ),
                }
            )

    groups.sort(
        key=lambda item: (item["post_count"], item["avg_engagement_rate"]),
        reverse=True,
    )
    state["trend_groups"] = groups
    return state
