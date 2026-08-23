"""Build competitor vs user content intelligence (topics, formats, opportunities)."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Callable

from agents.trend.Nodes.common import TOPIC_KEYWORDS
from agents.trend.services.content_analyzer import CONTENT_CATEGORY_KEYWORDS

_TOPIC_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AI", re.compile(r"\b(ai agents?|generative ai|machine learning|artificial intelligence|enterprise ai)\b", re.I)),
    ("Cloud", re.compile(r"\b(cloud consulting|cloud migration|cloud native|devops)\b", re.I)),
    ("Case Studies", re.compile(r"\b(case stud(?:y|ies)|client success|customer story|success story)\b", re.I)),
    ("Thought Leadership", re.compile(r"\b(thought leadership|industry insight|digital transformation)\b", re.I)),
    ("Cybersecurity", re.compile(r"\b(cybersecurity|security audit|penetration test)\b", re.I)),
    ("Software Development", re.compile(r"\b(software development|web development|mobile app)\b", re.I)),
    ("Automation", re.compile(r"\b(automation|workflow automation|rpa)\b", re.I)),
    ("Data Engineering", re.compile(r"\b(data engineering|data pipeline|analytics)\b", re.I)),
]

_FORMAT_ALIASES = {
    "reel": "Reels",
    "reels": "Reels",
    "video": "Reels",
    "carousel_album": "Carousel",
    "carousel": "Carousel",
    "image": "Image",
    "photo": "Image",
}


def _title_label(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "").strip())
    if not cleaned:
        return cleaned
    if cleaned.lower() in {"ai", "ml", "ui", "ux", "b2b", "saas"}:
        return cleaned.upper()
    return cleaned[0].upper() + cleaned[1:]


def _normalize_handle(value: Any) -> str:
    return str(value or "").strip().lstrip("@").lower()


def _normalize_media_type(post: dict[str, Any]) -> str:
    media_type = (post.get("media_type") or post.get("normalized_media_type") or "").upper()
    product_type = (post.get("media_product_type") or "").upper()
    if product_type == "REELS" or media_type in {"REEL", "VIDEO", "REELS"}:
        return "Reels"
    if media_type == "CAROUSEL_ALBUM":
        return "Carousel"
    if media_type == "IMAGE":
        return "Image"
    if media_type:
        return _FORMAT_ALIASES.get(media_type.lower(), _title_label(media_type))
    return "Unknown"


def _post_text(post: dict[str, Any]) -> str:
    caption = post.get("caption") or ""
    tags = " ".join(post.get("hashtags") or [])
    return f"{caption} {tags}".strip().lower()


def _topic_for_post(post: dict[str, Any]) -> str:
    existing = post.get("topic") or post.get("content_category") or post.get("primary_content_category")
    if existing and str(existing).strip().lower() not in {"", "general", "general brand"}:
        return _title_label(str(existing))

    text = _post_text(post)
    for label, pattern in _TOPIC_PATTERNS:
        if pattern.search(text):
            return label

    for category, keywords in CONTENT_CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return _title_label(category)

    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return _title_label(topic)

    if re.search(r"\bai\b", text):
        return "AI"

    return "General"


def _engagement_rate(post: dict[str, Any]) -> float:
    if post.get("engagement_rate") is not None:
        try:
            return float(post["engagement_rate"])
        except (TypeError, ValueError):
            pass
    followers = max(int(post.get("followers") or 0), 1)
    likes = int(post.get("likes") or post.get("like_count") or 0)
    comments = int(post.get("comments") or post.get("comments_count") or 0)
    return round(((likes + comments) / followers) * 100, 4)


def _normalize_post(post: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(post)
    normalized["engagement_rate"] = _engagement_rate(normalized)
    normalized["topic"] = _topic_for_post(normalized)
    normalized["format"] = _normalize_media_type(normalized)
    return normalized


def _user_handle(
    company_profile: dict[str, Any],
    company_analysis: dict[str, Any] | None,
    config: dict[str, Any] | None = None,
) -> str:
    profile = company_profile or {}
    analysis = company_analysis or {}
    cfg = config or {}
    return _normalize_handle(
        profile.get("instagram_username")
        or (analysis.get("user_instagram") or {}).get("username")
        or cfg.get("company_instagram_username")
        or cfg.get("company_username")
    )


def _collect_user_posts(
    *,
    company_analysis: dict[str, Any] | None,
    company_posts: list[dict[str, Any]] | None,
    processed_posts: list[dict[str, Any]],
    user_handle: str,
) -> list[dict[str, Any]]:
    analysis = company_analysis or {}
    user_block = analysis.get("user_instagram") or {}
    candidates = (
        list(company_posts or [])
        + list(analysis.get("instagram_posts") or [])
        + list(user_block.get("posts") or [])
    )

    seen_ids: set[str] = set()
    user_posts: list[dict[str, Any]] = []
    for post in candidates:
        post_id = str(post.get("id") or post.get("media_id") or "")
        if post_id and post_id in seen_ids:
            continue
        if post_id:
            seen_ids.add(post_id)
        user_posts.append(_normalize_post(post))

    for post in processed_posts or []:
        username = _normalize_handle(post.get("username"))
        if user_handle and username == user_handle:
            post_id = str(post.get("id") or post.get("media_id") or "")
            if post_id and post_id in seen_ids:
                continue
            if post_id:
                seen_ids.add(post_id)
            user_posts.append(_normalize_post(post))

    return user_posts


def _collect_competitor_posts(
    processed_posts: list[dict[str, Any]],
    user_handle: str,
) -> list[dict[str, Any]]:
    competitor_posts: list[dict[str, Any]] = []
    for post in processed_posts or []:
        username = _normalize_handle(post.get("username"))
        if user_handle and username == user_handle:
            continue
        competitor_posts.append(_normalize_post(post))
    return competitor_posts


def _usage_rows(
    *,
    competitor_posts: list[dict[str, Any]],
    user_posts: list[dict[str, Any]],
    label_fn: Callable[[dict[str, Any]], str],
    label_key: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    competitor_counts: Counter[str] = Counter(label_fn(post) for post in competitor_posts)
    user_counts: Counter[str] = Counter(label_fn(post) for post in user_posts)
    competitor_total = len(competitor_posts)
    user_total = len(user_posts)
    keys = set(competitor_counts) | set(user_counts)

    rows: list[dict[str, Any]] = []
    for key in keys:
        if key.lower() in {"general", "unknown"}:
            continue
        competitor_usage = round((competitor_counts.get(key, 0) / max(competitor_total, 1)) * 100)
        user_usage = round((user_counts.get(key, 0) / max(user_total, 1)) * 100)
        rows.append(
            {
                label_key: key,
                "competitor_usage": competitor_usage,
                "user_usage": user_usage,
                "gap": competitor_usage - user_usage,
            }
        )

    rows.sort(key=lambda row: (row["gap"], row["competitor_usage"]), reverse=True)
    return rows[:limit]


def _performing_rows(
    *,
    posts: list[dict[str, Any]],
    label_fn: Callable[[dict[str, Any]], str],
    label_key: str,
    usage_lookup: dict[str, dict[str, int]],
    limit: int = 8,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for post in posts:
        label = label_fn(post)
        if label.lower() in {"general", "unknown"}:
            continue
        grouped[label].append(float(post.get("engagement_rate") or 0))

    rows: list[dict[str, Any]] = []
    for label, rates in grouped.items():
        if not rates:
            continue
        usage = usage_lookup.get(label, {})
        rows.append(
            {
                label_key: label,
                "avg_engagement": round(sum(rates) / len(rates), 2),
                "post_count": len(rates),
                "competitor_usage": usage.get("competitor_usage", 0),
                "user_usage": usage.get("user_usage", 0),
                "gap": usage.get("gap", 0),
            }
        )

    rows.sort(key=lambda row: (row["avg_engagement"], row["gap"]), reverse=True)
    return rows[:limit]


def _priority_from_gap(gap: int, avg_engagement: float = 0.0) -> str:
    if gap >= 25 or (gap >= 15 and avg_engagement >= 2.0):
        return "high"
    if gap >= 10 or avg_engagement >= 1.5:
        return "medium"
    return "low"


def _content_opportunities(
    *,
    top_topics: list[dict[str, Any]],
    top_formats: list[dict[str, Any]],
    top_performing_topics: list[dict[str, Any]],
    top_performing_formats: list[dict[str, Any]],
    competitor_posts: list[dict[str, Any]],
    limit: int = 8,
) -> list[dict[str, Any]]:
    topic_engagement = {
        row["topic"]: float(row.get("avg_engagement") or 0)
        for row in top_performing_topics
        if row.get("topic")
    }
    format_engagement = {
        row["format"]: float(row.get("avg_engagement") or 0)
        for row in top_performing_formats
        if row.get("format")
    }

    opportunities: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for topic_row in top_topics:
        if topic_row.get("gap", 0) <= 0:
            continue
        topic = topic_row["topic"]
        best_format = None
        best_format_gap = -1
        for fmt_row in top_formats:
            if fmt_row.get("gap", 0) <= 0:
                continue
            pair_key = (topic, fmt_row["format"])
            if pair_key in seen:
                continue
            score = fmt_row["gap"] + topic_row["gap"]
            if score > best_format_gap:
                best_format_gap = score
                best_format = fmt_row["format"]

        if not best_format:
            best_format = (top_formats[0]["format"] if top_formats else "Reels")

        pair_key = (topic, best_format)
        if pair_key in seen:
            continue
        seen.add(pair_key)

        avg_engagement = max(topic_engagement.get(topic, 0.0), format_engagement.get(best_format, 0.0))
        opportunities.append(
            {
                "topic": topic,
                "format": best_format,
                "competitor_usage": topic_row.get("competitor_usage", 0),
                "user_usage": topic_row.get("user_usage", 0),
                "gap": topic_row.get("gap", 0),
                "avg_engagement": round(avg_engagement, 2),
                "priority": _priority_from_gap(int(topic_row.get("gap") or 0), avg_engagement),
            }
        )

    if not opportunities and competitor_posts:
        for topic_row in top_topics[:5]:
            if topic_row.get("gap", 0) <= 5:
                continue
            opportunities.append(
                {
                    "topic": topic_row["topic"],
                    "format": (top_formats[0]["format"] if top_formats else "Reels"),
                    "competitor_usage": topic_row.get("competitor_usage", 0),
                    "user_usage": topic_row.get("user_usage", 0),
                    "gap": topic_row.get("gap", 0),
                    "avg_engagement": round(topic_engagement.get(topic_row["topic"], 0.0), 2),
                    "priority": _priority_from_gap(int(topic_row.get("gap") or 0)),
                }
            )

    opportunities.sort(
        key=lambda row: (row.get("gap", 0), row.get("avg_engagement", 0)),
        reverse=True,
    )
    return opportunities[:limit]


def build_competitive_content_intelligence(
    *,
    company_profile: dict[str, Any],
    company_analysis: dict[str, Any] | None = None,
    processed_posts: list[dict[str, Any]] | None = None,
    company_posts: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare user vs competitor content usage by topic and format."""
    user_handle = _user_handle(company_profile, company_analysis, config)
    user_posts = _collect_user_posts(
        company_analysis=company_analysis,
        company_posts=company_posts,
        processed_posts=processed_posts or [],
        user_handle=user_handle,
    )
    competitor_posts = _collect_competitor_posts(processed_posts or [], user_handle)

    top_topics = _usage_rows(
        competitor_posts=competitor_posts,
        user_posts=user_posts,
        label_fn=lambda post: str(post.get("topic") or "General"),
        label_key="topic",
    )
    top_formats = _usage_rows(
        competitor_posts=competitor_posts,
        user_posts=user_posts,
        label_fn=lambda post: str(post.get("format") or "Unknown"),
        label_key="format",
    )

    topic_usage_lookup = {row["topic"]: row for row in top_topics}
    format_usage_lookup = {row["format"]: row for row in top_formats}

    top_performing_topics = _performing_rows(
        posts=competitor_posts,
        label_fn=lambda post: str(post.get("topic") or "General"),
        label_key="topic",
        usage_lookup=topic_usage_lookup,
    )
    top_performing_formats = _performing_rows(
        posts=competitor_posts,
        label_fn=lambda post: str(post.get("format") or "Unknown"),
        label_key="format",
        usage_lookup=format_usage_lookup,
    )

    content_opportunities = _content_opportunities(
        top_topics=top_topics,
        top_formats=top_formats,
        top_performing_topics=top_performing_topics,
        top_performing_formats=top_performing_formats,
        competitor_posts=competitor_posts,
    )

    return {
        "top_topics": top_topics,
        "top_formats": top_formats,
        "top_performing_topics": top_performing_topics,
        "top_performing_formats": top_performing_formats,
        "content_opportunities": content_opportunities,
    }
