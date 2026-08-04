from collections import defaultdict

from agents.trend.Nodes.common import TOPIC_KEYWORDS
from agents.competitor.state.competitor_state import CompetitorState


def TopiForText(text: str) -> str:
    lowered = (text or "").lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return topic
    return "General"


async def ClassifyTopicsNode(state: CompetitorState) -> CompetitorState:
    topic_posts: dict[str, list[dict]] = defaultdict(list)

    for post in state.get("processed_posts") or []:
        caption = post.get("caption") or ""
        tags = " ".join(post.get("hashtags") or [])
        topic = TopiForText(f"{caption} {tags}")
        topic_posts[topic].append(post)

    state["topics"] = [
        {
            "topic": topic,
            "post_count": len(posts),
            "creator_count": len({post.get("username") for post in posts if post.get("username")}),
        }
        for topic, posts in sorted(
            topic_posts.items(),
            key=lambda item: len(item[1]),
            reverse=True,
        )
    ]
    return state
