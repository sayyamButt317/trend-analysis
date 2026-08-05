from collections import Counter
from typing import Any

from agents.trend.services.content_analyzer import (
    analyze_caption_style,
    classify_content_category,
    normalize_media_type,
)


def analyze_media_mix(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = len(posts)
    if not total:
        return []
    media_counts = Counter(normalize_media_type(post) for post in posts)
    return [
        {
            "type": media_type,
            "format": media_type,
            "count": count,
            "share_pct": round((count / total) * 100, 1),
        }
        for media_type, count in media_counts.most_common()
    ]


def analyze_content_categories(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = len(posts)
    if not total:
        return []

    category_counts = Counter(
        classify_content_category(post.get("caption") or post.get("text") or "", post.get("hashtags") or [])
        for post in posts
    )
    return [
        {
            "category": category,
            "count": count,
            "share_pct": round((count / total) * 100, 1),
        }
        for category, count in category_counts.most_common()
    ]


def analyze_caption_style_summary(posts: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(posts)
    if not total:
        return {}

    caption_styles = [analyze_caption_style(post.get("caption") or post.get("text") or "") for post in posts]
    return {
        "avg_caption_length": round(
            sum(style["caption_length"] for style in caption_styles) / total,
            1,
        ),
        "question_posts_pct": round(
            sum(1 for style in caption_styles if style["has_question"]) / total * 100,
            1,
        ),
        "cta_posts_pct": round(
            sum(1 for style in caption_styles if style["has_cta"]) / total * 100,
            1,
        ),
        "emoji_posts_pct": round(
            sum(1 for style in caption_styles if style["uses_emojis"]) / total * 100,
            1,
        ),
    }


def build_content_focus(
    media_mix: list[dict[str, Any]],
    content_categories: list[dict[str, Any]],
) -> str | None:
    focus_parts: list[str] = []
    if media_mix:
        primary = media_mix[0]
        focus_parts.append(f"Mostly {primary['type']} ({primary['share_pct']}%)")
    if content_categories:
        primary_category = content_categories[0]["category"]
        if primary_category != "General Brand":
            focus_parts.append(
                f"focused on {primary_category} ({content_categories[0]['share_pct']}%)"
            )
    return ". ".join(focus_parts) if focus_parts else None
