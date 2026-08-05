import logging
from typing import Any

from agents.trend.Nodes.common import HASHTAG_RE
from agents.trend.services.instagram_discovery import fetch_instagram_profile
from agents.trend.services.instagramuser_details import InstagramRateLimitError

logger = logging.getLogger(__name__)


def normalize_username(value: str | None) -> str | None:
    username = (value or "").strip().lstrip("@").lower()
    return username or None


def normalize_media_type(media_type: str, product_type: str = "") -> str:
    media = (media_type or "").upper()
    product = (product_type or "").upper()
    if product == "REELS" or media in {"REEL", "VIDEO", "REELS"}:
        return "Reels"
    if media == "CAROUSEL_ALBUM":
        return "Carousel"
    if media == "IMAGE":
        return "Image"
    return media.title() if media else "Unknown"


def _first_int(post: dict[str, Any], *keys: str) -> int:
    for key in keys:
        if key in post and post[key] is not None:
            try:
                return int(post[key])
            except (TypeError, ValueError):
                return 0
    return 0


def normalize_post(item: dict[str, Any], *, profile: dict[str, Any], handle: str) -> dict[str, Any]:
    followers = int(profile.get("followers_count") or 0)
    caption = item.get("caption") or ""
    normalized_media_type = normalize_media_type(
        item.get("media_type") or "",
        item.get("media_product_type") or "",
    )
    return {
        **item,
        "id": item.get("id"),
        "media_id": item.get("id"),
        "username": profile.get("username") or handle,
        "name": profile.get("name"),
        "caption": caption,
        "text": caption,
        "hashtags": [tag.lower() for tag in HASHTAG_RE.findall(caption)],
        "likes": _first_int(item, "likes", "like_count"),
        "comments": _first_int(item, "comments", "comments_count"),
        "views": _first_int(item, "views", "view_count", "play_count"),
        "followers": followers,
        "followers_count": followers,
        "normalized_media_type": normalized_media_type,
        "media_type": normalized_media_type,
    }


def posts_from_profile(profile: dict[str, Any], *, handle: str) -> list[dict[str, Any]]:
    media_items = (profile.get("media") or {}).get("data") or profile.get("posts") or []
    return [normalize_post(item, profile=profile, handle=handle) for item in media_items]


async def fetch_user_instagram_profile(
    username: str,
    *,
    post_limit: int = 10,
) -> dict[str, Any] | None:
    handle = normalize_username(username)
    if not handle:
        return None
    try:
        return await fetch_instagram_profile(handle, post_limit=post_limit)
    except InstagramRateLimitError:
        raise
    except Exception:
        logger.exception("User Instagram fetch failed for @%s", handle)
        return None
