import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

HASHTAG_RE = re.compile(r"#(\w+)")
MENTION_RE = re.compile(r"@([A-Za-z0-9._]+)")

TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Fashion": ("fashion", "style", "outfit", "ootd"),
    "Beauty": ("beauty", "makeup", "skincare", "grwm"),
    "Food": ("food", "recipe", "restaurant", "cafe"),
    "Travel": ("travel", "trip", "hotel", "vacation"),
    "Fitness": ("fitness", "gym", "workout", "health"),
    "Luxury": ("luxury", "designer", "premium"),
    "Lifestyle": ("lifestyle", "vlog", "daily", "life"),
}

GENERIC_HASHTAGS = {
    "instagram",
    "reels",
    "reel",
    "explore",
    "viral",
    "love",
    "instagood",
    "photooftheday",
}


def parse_timestamp(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
