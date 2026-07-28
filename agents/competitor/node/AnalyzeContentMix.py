from collections import Counter, defaultdict

from agents.trend.Nodes.common import TOPIC_KEYWORDS
from agents.trend.services.content_analyzer import enrich_content_insights
from agents.trend.state.trend_state import TrendState


def normalize_media_type(post: dict) -> str:
    media_type = (post.get("media_type") or post.get("normalized_media_type") or "").upper()
    product_type = (post.get("media_product_type") or "").upper()
    if product_type == "REELS" or media_type in {"REEL", "VIDEO", "REELS"}:
        return "Reels"
    if media_type == "CAROUSEL_ALBUM":
        return "Carousel"
    if media_type == "IMAGE":
        return "Image"
    return media_type.title() if media_type else "Unknown"


def topic_for_text(text: str) -> str:
    lowered = (text or "").lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return topic
    return "General"


def _build_base_content_profile(username: str, posts: list[dict]) -> dict:
    total = len(posts)
    media_counts = Counter(normalize_media_type(post) for post in posts)
    topic_counts = Counter(
        topic_for_text(f"{post.get('caption') or ''} {' '.join(post.get('hashtags') or [])}")
        for post in posts
    )

    return {
        "username": username,
        "post_count": total,
        "media_types": [
            {
                "type": media_type,
                "count": count,
                "share_pct": round((count / total) * 100, 1),
            }
            for media_type, count in media_counts.most_common()
        ],
        "content_themes": [
            {
                "theme": theme,
                "count": count,
                "share_pct": round((count / total) * 100, 1),
            }
            for theme, count in topic_counts.most_common()
        ],
        "top_hashtags": [
            tag
            for tag, _count in Counter(
                tag for post in posts for tag in (post.get("hashtags") or [])
            ).most_common(5)
        ],
        "avg_engagement_rate": round(
            sum(float(post.get("engagement_rate") or 0) for post in posts) / max(total, 1),
            4,
        ),
    }


async def AnalyzeContentMixNode(state: TrendState) -> TrendState:
    by_competitor: dict[str, list[dict]] = defaultdict(list)
    for post in state.get("processed_posts") or []:
        username = post.get("username")
        if username:
            by_competitor[username].append(post)

    content_mix: list[dict] = []
    for username, posts in sorted(by_competitor.items()):
        profile = _build_base_content_profile(username, posts)
        content_mix.append(enrich_content_insights(posts, profile))

    state["content_mix"] = content_mix
    return state
