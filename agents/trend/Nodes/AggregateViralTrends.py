from collections import defaultdict

from agents.trend.Nodes.common import TOPIC_KEYWORDS
from agents.trend.state.trend_state import TrendState


def _topic_for_text(text: str) -> str:
    lowered = (text or "").lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return topic
    return "General"


def _is_reel(post: dict) -> bool:
    product_type = (post.get("media_product_type") or "").upper()
    media_type = (post.get("media_type") or "").upper()
    return product_type == "REELS" or media_type in {"VIDEO", "REEL"}


async def AggregateViralTrendsNode(state: TrendState) -> TrendState:
    viral_posts = state.get("viral_posts") or []
    influencer_categories: dict[str, list[str]] = {}
    for influencer in state.get("discovered_influencers") or []:
        username = (influencer.get("username") or "").lower()
        categories = influencer.get("category") or []
        if username and categories:
            influencer_categories[username] = [
                str(item).strip() for item in categories if str(item).strip()
            ]

    sound_groups: dict[str, dict] = {}
    category_groups: dict[str, dict] = {}

    for post in viral_posts:
        username = (post.get("username") or "").lower()
        caption = post.get("caption") or ""
        tags = " ".join(post.get("hashtags") or [])
        topic = _topic_for_text(f"{caption} {tags}")

        categories = set(influencer_categories.get(username) or [])
        categories.add(topic)

        for category in categories:
            entry = category_groups.setdefault(
                category,
                {
                    "category": category,
                    "viral_post_count": 0,
                    "creators": set(),
                    "total_engagement_rate": 0.0,
                    "total_views": 0,
                    "hashtags": defaultdict(int),
                },
            )
            entry["viral_post_count"] += 1
            entry["creators"].add(username)
            entry["total_engagement_rate"] += float(post.get("engagement_rate") or 0)
            entry["total_views"] += int(post.get("views") or 0)
            for tag in post.get("hashtags") or []:
                entry["hashtags"][str(tag).lower()] += 1

        if not _is_reel(post):
            continue

        audio_type = (post.get("media_audio_type") or "UNKNOWN").upper()
        sound_entry = sound_groups.setdefault(
            audio_type,
            {
                "audio_type": audio_type,
                "viral_reel_count": 0,
                "creators": set(),
                "total_engagement_rate": 0.0,
                "total_views": 0,
                "top_posts": [],
            },
        )
        sound_entry["viral_reel_count"] += 1
        sound_entry["creators"].add(username)
        sound_entry["total_engagement_rate"] += float(post.get("engagement_rate") or 0)
        sound_entry["total_views"] += int(post.get("views") or 0)
        sound_entry["top_posts"].append(
            {
                "media_id": post.get("media_id"),
                "username": username,
                "permalink": post.get("permalink"),
                "views": int(post.get("views") or 0),
                "likes": int(post.get("likes") or 0),
                "comments": int(post.get("comments") or 0),
                "engagement_rate": float(post.get("engagement_rate") or 0),
                "media_audio_type": audio_type,
                "caption_preview": caption[:120],
            }
        )

    viral_categories: list[dict] = []
    for category, entry in category_groups.items():
        count = max(entry["viral_post_count"], 1)
        top_hashtags = sorted(
            entry["hashtags"].items(),
            key=lambda item: item[1],
            reverse=True,
        )[:5]
        viral_categories.append(
            {
                "category": category,
                "viral_post_count": entry["viral_post_count"],
                "creator_count": len(entry["creators"]),
                "avg_engagement_rate": round(entry["total_engagement_rate"] / count, 4),
                "total_views": entry["total_views"],
                "top_hashtags": [tag for tag, _count in top_hashtags],
            }
        )
    viral_categories.sort(
        key=lambda item: (item["viral_post_count"], item["avg_engagement_rate"]),
        reverse=True,
    )

    viral_sounds: list[dict] = []
    for audio_type, entry in sound_groups.items():
        count = max(entry["viral_reel_count"], 1)
        top_posts = sorted(
            entry["top_posts"],
            key=lambda item: (
                float(item.get("engagement_rate") or 0),
                int(item.get("views") or 0),
            ),
            reverse=True,
        )[:5]
        viral_sounds.append(
            {
                "audio_type": audio_type,
                "label": "Licensed Music" if audio_type == "MUSIC" else "Original Sound",
                "viral_reel_count": entry["viral_reel_count"],
                "creator_count": len(entry["creators"]),
                "avg_engagement_rate": round(entry["total_engagement_rate"] / count, 4),
                "total_views": entry["total_views"],
                "top_posts": top_posts,
            }
        )
    viral_sounds.sort(
        key=lambda item: (item["viral_reel_count"], item["total_views"]),
        reverse=True,
    )

    state["viral_categories"] = viral_categories
    state["viral_sounds"] = viral_sounds
    return state
