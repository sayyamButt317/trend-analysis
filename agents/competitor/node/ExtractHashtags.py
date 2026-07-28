from collections import Counter

from agents.trend.Nodes.common import GENERIC_HASHTAGS
from agents.trend.state.trend_state import TrendState


async def ExtractHashtagsNode(state: TrendState) -> TrendState:
    counter: Counter[str] = Counter()
    creators_by_tag: dict[str, set[str]] = {}

    for post in state.get("processed_posts") or []:
        username = post.get("username") or ""
        for tag in post.get("hashtags") or []:
            normalized = str(tag).lower().strip()
            if not normalized or normalized in GENERIC_HASHTAGS:
                continue
            counter[normalized] += 1
            creators_by_tag.setdefault(normalized, set()).add(username)

    state["hashtags"] = [
        {
            "hashtag": tag,
            "post_count": count,
            "creator_count": len(creators_by_tag.get(tag, set())),
        }
        for tag, count in counter.most_common()
    ]
    return state
