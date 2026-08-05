from collections import Counter
from typing import Any

from agents.trend.Nodes.common import GENERIC_HASHTAGS, HASHTAG_RE


def extract_hashtag_tags(posts: list[dict[str, Any]]) -> list[str]:
    tags: list[str] = []
    for post in posts:
        for tag in post.get("hashtags") or []:
            if isinstance(tag, dict):
                value = tag.get("tag") or tag.get("hashtag") or ""
            else:
                value = str(tag)
            normalized = value.lower().strip().lstrip("#")
            if normalized:
                tags.append(normalized)
        caption = post.get("caption") or post.get("text") or ""
        for tag in HASHTAG_RE.findall(caption):
            normalized = tag.lower().strip()
            if normalized:
                tags.append(normalized)
    return tags


def analyze_hashtags(posts: list[dict[str, Any]], *, limit: int = 10) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for tag in extract_hashtag_tags(posts):
        if tag in GENERIC_HASHTAGS:
            continue
        counter[tag] += 1
    return [{"tag": tag, "count": count} for tag, count in counter.most_common(limit)]
