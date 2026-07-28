import re
from collections import Counter
from typing import Any

CONTENT_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Thought Leadership": (
        "thought leadership",
        "industry trend",
        "insights",
        "digital transformation",
        "innovation",
        "future of",
        "ai ",
        " artificial intelligence",
        "machine learning",
        "technology",
        "tech trend",
    ),
    "Case Studies": (
        "case study",
        "success story",
        "client project",
        "we built",
        "we delivered",
        "portfolio",
        "project launch",
        "our work",
        "proud to",
    ),
    "Hiring & Careers": (
        "we're hiring",
        "we are hiring",
        "join our team",
        "job opening",
        "careers",
        "hiring",
        "vacancy",
        "apply now",
        "open position",
        "internship",
    ),
    "Product & Services": (
        "our solution",
        "our service",
        "we offer",
        "introducing",
        "product launch",
        "new feature",
        "platform",
        "software",
        "app development",
        "staff augmentation",
    ),
    "Team & Culture": (
        "team",
        "office",
        "behind the scenes",
        "culture",
        "meet the team",
        "employee",
        "workplace",
        "company culture",
        "our people",
    ),
    "Educational": (
        "tips",
        "how to",
        "guide",
        "tutorial",
        "learn",
        "did you know",
        "explained",
        "step by step",
        "best practices",
    ),
    "Events & Webinars": (
        "webinar",
        "event",
        "conference",
        "summit",
        "workshop",
        "meetup",
        "register",
        "live session",
    ),
    "Client Testimonials": (
        "testimonial",
        "client feedback",
        "review",
        "what our clients",
        "client say",
        "trusted by",
    ),
    "Promotional": (
        "offer",
        "discount",
        "limited time",
        "free consultation",
        "book a call",
        "contact us",
        "dm us",
        "link in bio",
    ),
}

CTA_PATTERNS = (
    "contact us",
    "dm us",
    "link in bio",
    "book a",
    "learn more",
    "sign up",
    "register",
    "apply now",
    "visit our",
    "click the link",
)

EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "]+",
    flags=re.UNICODE,
)


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


def classify_content_category(caption: str, hashtags: list[str] | None = None) -> str:
    text = f"{caption or ''} {' '.join(hashtags or [])}".lower()
    best_category = "General Brand"
    best_hits = 0
    for category, keywords in CONTENT_CATEGORY_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword in text)
        if hits > best_hits:
            best_hits = hits
            best_category = category
    return best_category


def analyze_caption_style(caption: str) -> dict[str, Any]:
    text = caption or ""
    lowered = text.lower()
    emoji_count = len(EMOJI_RE.findall(text))
    return {
        "caption_length": len(text),
        "has_question": "?" in text,
        "has_cta": any(pattern in lowered for pattern in CTA_PATTERNS),
        "emoji_count": emoji_count,
        "uses_emojis": emoji_count > 0,
    }


def _best_engagement_format(posts: list[dict]) -> dict | None:
    by_format: dict[str, list[float]] = {}
    for post in posts:
        fmt = normalize_media_type(post)
        by_format.setdefault(fmt, []).append(float(post.get("engagement_rate") or 0))
    if not by_format:
        return None
    ranked = sorted(
        (
            {
                "format": fmt,
                "avg_engagement_rate": round(sum(rates) / len(rates), 4),
                "post_count": len(rates),
            }
            for fmt, rates in by_format.items()
        ),
        key=lambda item: item["avg_engagement_rate"],
        reverse=True,
    )
    return ranked[0] if ranked else None


def enrich_content_insights(posts: list[dict], profile: dict[str, Any]) -> dict[str, Any]:
    """Add business content insights without changing the original media/theme fields."""
    total = len(posts)
    if total == 0:
        return {
            **profile,
            "content_categories": [],
            "primary_format": None,
            "primary_content_category": None,
            "content_focus": None,
            "caption_style": {},
            "best_performing_format": None,
        }

    category_counts = Counter(
        classify_content_category(post.get("caption") or "", post.get("hashtags") or [])
        for post in posts
    )
    content_categories = [
        {"category": category, "count": count, "share_pct": round((count / total) * 100, 1)}
        for category, count in category_counts.most_common()
    ]

    caption_styles = [analyze_caption_style(post.get("caption") or "") for post in posts]
    media_types = profile.get("media_types") or []
    primary_format = media_types[0]["type"] if media_types else None
    primary_category = content_categories[0]["category"] if content_categories else None

    focus_parts = []
    if primary_format:
        focus_parts.append(f"Mostly {primary_format} ({media_types[0]['share_pct']}%)")
    if primary_category and primary_category != "General Brand":
        focus_parts.append(f"focused on {primary_category} ({content_categories[0]['share_pct']}%)")

    return {
        **profile,
        "content_categories": content_categories,
        "primary_format": primary_format,
        "primary_content_category": primary_category,
        "content_focus": ". ".join(focus_parts) if focus_parts else None,
        "caption_style": {
            "avg_caption_length": round(
                sum(style["caption_length"] for style in caption_styles) / total,
                1,
            ),
            "question_posts_pct": round(
                sum(1 for s in caption_styles if s["has_question"]) / total * 100,
                1,
            ),
            "cta_posts_pct": round(
                sum(1 for s in caption_styles if s["has_cta"]) / total * 100,
                1,
            ),
            "emoji_posts_pct": round(
                sum(1 for s in caption_styles if s["uses_emojis"]) / total * 100,
                1,
            ),
        },
        "best_performing_format": _best_engagement_format(posts),
    }


def build_market_content_usage(
    content_mix: list[dict],
    processed_posts: list[dict],
) -> dict[str, Any]:
    if not processed_posts:
        return {
            "summary": "No competitor posts were available to analyze content usage.",
            "format_breakdown": [],
            "category_breakdown": [],
            "most_used_format": None,
            "most_used_category": None,
            "insights": [],
        }

    format_counts = Counter()
    category_counts = Counter()
    competitors_using_reels = 0
    competitors_using_carousel = 0

    for profile in content_mix:
        for item in profile.get("media_types") or []:
            format_counts[item["type"]] += item.get("count", 0)
            if item["type"] == "Reels" and item.get("count", 0) > 0:
                competitors_using_reels += 1
            if item["type"] == "Carousel" and item.get("count", 0) > 0:
                competitors_using_carousel += 1
        for item in profile.get("content_categories") or []:
            category_counts[item["category"]] += item.get("count", 0)

    total_posts = len(processed_posts)
    format_breakdown = [
        {
            "format": fmt,
            "count": count,
            "share_pct": round((count / total_posts) * 100, 1),
        }
        for fmt, count in format_counts.most_common()
    ]
    category_breakdown = [
        {
            "category": category,
            "count": count,
            "share_pct": round((count / total_posts) * 100, 1),
        }
        for category, count in category_counts.most_common()
    ]

    most_used_format = format_breakdown[0]["format"] if format_breakdown else None
    most_used_category = category_breakdown[0]["category"] if category_breakdown else None
    competitor_count = len(content_mix)

    insights: list[str] = []
    if most_used_format and format_breakdown:
        insights.append(
            f"{format_breakdown[0]['share_pct']}% of analyzed posts are {most_used_format}."
        )
    if competitor_count and competitors_using_reels:
        insights.append(
            f"{competitors_using_reels} of {competitor_count} competitors actively use Reels."
        )
    if competitor_count and competitors_using_carousel:
        insights.append(
            f"{competitors_using_carousel} of {competitor_count} competitors use Carousel posts."
        )
    if most_used_category and most_used_category != "General Brand":
        insights.append(
            f"The most common business content type is {most_used_category} "
            f"({category_breakdown[0]['share_pct']}% of posts)."
        )

    summary_parts = []
    if most_used_format:
        share = format_breakdown[0]["share_pct"]
        summary_parts.append(f"Competitors mainly use {most_used_format} ({share}% of posts)")
    if most_used_category and most_used_category != "General Brand":
        cat_share = category_breakdown[0]["share_pct"]
        summary_parts.append(f"with emphasis on {most_used_category} content ({cat_share}%)")

    return {
        "summary": ". ".join(summary_parts) + "." if summary_parts else "Mixed content patterns across competitors.",
        "format_breakdown": format_breakdown,
        "category_breakdown": category_breakdown,
        "most_used_format": most_used_format,
        "most_used_category": most_used_category,
        "insights": insights[:8],
    }
