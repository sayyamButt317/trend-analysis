import re
from typing import Any

THOUGHT_LEADERSHIP_PATTERNS = (
    r"\b(thought leadership|industry insight|market trend|future of)\b",
    r"\b(opinion|perspective|take on|we believe)\b",
    r"\b(research|report|study|survey|data shows)\b",
    r"\b(innovation|transformation|disruption|strategy)\b",
    r"\b(lessons? learned|key takeaway|framework)\b",
)


def analyze_thought_leadership(posts: list[dict[str, Any]]) -> dict[str, Any]:
    if not posts:
        return {
            "thought_leadership_score": 0.0,
            "thought_leadership_posts": 0,
            "signals": [],
        }

    matched_posts = 0
    signals: list[str] = []
    for post in posts:
        text = (post.get("text") or post.get("title") or "").lower()
        if not text:
            continue
        hits = [pattern for pattern in THOUGHT_LEADERSHIP_PATTERNS if re.search(pattern, text, re.I)]
        if hits:
            matched_posts += 1
            signals.extend(hits)

    score = round((matched_posts / len(posts)) * 100, 1)
    unique_signals = list(dict.fromkeys(signals))[:8]
    return {
        "thought_leadership_score": score,
        "thought_leadership_posts": matched_posts,
        "signals": unique_signals,
        "is_thought_leader": score >= 25,
    }
