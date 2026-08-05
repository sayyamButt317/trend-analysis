import re
from collections import Counter
from typing import Any
from agents.trend.services.content_analyzer import classify_content_category

LINKEDIN_THEME_PATTERNS = (
    r"\b(hiring|we're hiring|join our team|career)\b",
    r"\b(product launch|new feature|announcement|proud to)\b",
    r"\b(case study|client success|customer story)\b",
    r"\b(tips?|how to|guide|best practices?)\b",
    r"\b(industry trend|market|growth|innovation)\b",
)


def extract_linkedin_themes(posts: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    theme_counts: Counter[str] = Counter()
    for post in posts:
        text = (post.get("text") or post.get("title") or "").lower()
        if not text:
            continue
        for pattern in LINKEDIN_THEME_PATTERNS:
            if re.search(pattern, text, re.I):
                theme_counts[pattern] += 1
        category = classify_content_category(text, [])
        if category and category != "General Brand":
            theme_counts[category] += 1
    return [{"theme": theme, "count": count} for theme, count in theme_counts.most_common(limit)]
