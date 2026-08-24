import asyncio
import logging
from agents.trend.services.instagramuser_details import (
    ExtractInfluencerDetailsFromInstagram,
    InstagramRateLimitError,
)
from config.credential_config import config
from scrapper.instagram_finder.constants import SUPPORTED_COUNTRIES, normalize_categories
from scrapper.instagram_finder.finder import find_gcc_influencers
from scrapper.instagram_finder.validator import is_valid_instagram_username

logger = logging.getLogger(__name__)

PLACEHOLDER_USERNAMES = frozenset(
    {"string", "username", "handle", "example", "test", "null", "none"}
)


def normalize_instagram_usernames(seed_usernames: list[str] | None) -> list[str] | None:
    if not seed_usernames:
        return None
    cleaned: list[str] = []
    seen: set[str] = set()
    for username in seed_usernames:
        handle = (username or "").strip().lstrip("@").lower()
        if not handle or handle in PLACEHOLDER_USERNAMES:
            continue
        if not is_valid_instagram_username(handle):
            continue
        if handle in seen:
            continue
        seen.add(handle)
        cleaned.append(handle)
    return cleaned or None


def _normalize_media_type(media_type: str, product_type: str = "") -> str:
    media = (media_type or "").upper()
    product = (product_type or "").upper()
    if product == "REELS" or media in {"REEL", "VIDEO"}:
        return "Reels"
    if media == "CAROUSEL_ALBUM":
        return "Carousel"
    if media == "IMAGE":
        return "Image"
    return media.title() if media else "Unknown"


async def fetch_instagram_profile(username: str, *, post_limit: int = 25) -> dict | None:
    try:
        profile = await ExtractInfluencerDetailsFromInstagram(username, post_limit=post_limit)
    except InstagramRateLimitError:
        raise
    except Exception:
        logger.warning("Instagram profile fetch failed for @%s", username, exc_info=True)
        return None

    if not profile:
        return None

    media_count = len((profile or {}).get("media", {}).get("data") or [])
    if media_count:
        logger.info(
            "[discovery] Instagram profile @%s returned %s posts",
            username,
            media_count,
        )
    else:
        logger.warning(
            "[discovery] Instagram profile returned no posts for @%s",
            username,
        )
    return profile


async def fetch_instagram_posts_for_usernames(
    usernames: list[str],
    *,
    influencer_by_username: dict[str, dict] | None = None,
    delay_seconds: float = 1.0,
    post_limit: int = 25,
    return_profiles: bool = False,
) -> list[dict] | tuple[list[dict], dict[str, dict]]:
    influencer_by_username = influencer_by_username or {}
    posts: list[dict] = []
    profiles_by_username: dict[str, dict] = {}
    failed: list[str] = []

    for username in usernames:
        handle = (username or "").strip().lstrip("@").lower()
        if not handle:
            continue
        try:
            profile = await fetch_instagram_profile(handle, post_limit=post_limit)
        except InstagramRateLimitError:
            logger.error("Instagram rate limit hit while fetching @%s", handle)
            raise
        except Exception:
            logger.warning("Instagram fetch failed for @%s", handle)
            failed.append(handle)
            continue

        if not profile:
            failed.append(handle)
            continue

        profiles_by_username[handle] = profile
        meta = influencer_by_username.get(handle) or {}
        followers = int(profile.get("followers_count") or 0)
        media_items = (profile.get("media") or {}).get("data") or []

        for item in media_items:
            normalized_media_type = _normalize_media_type(
                item.get("media_type") or "",
                item.get("media_product_type") or "",
            )
            posts.append(
                {
                    **item,
                    "id": item.get("id"),
                    "media_id": item.get("id"),
                    "username": profile.get("username") or handle,
                    "name": profile.get("name"),
                    "followers": followers,
                    "followers_count": followers,
                    "influencer": meta,
                    "source_username": handle,
                    "normalized_media_type": normalized_media_type,
                }
            )

        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

    if failed:
        logger.warning(
            "Instagram fetch failed or timed out for %s account(s): %s",
            len(failed),
            ", ".join(failed[:10]),
        )

    if return_profiles:
        return posts, profiles_by_username
    return posts


async def discover_influencers_via_instagram(
    *,
    country: str | None = None,
    categories: list[str] | None = None,
    limit: int = 20,
) -> list[dict]:
    countries = [country] if country else list(SUPPORTED_COUNTRIES)
    logger.info(
        "Discovering Instagram influencers via live search for: %s (categories=%s)",
        ", ".join(countries),
        categories or "all",
    )
    result = await find_gcc_influencers(
        countries=countries,
        categories=categories,
        max_count=limit,
        enrich_profiles=True,
    )
    if not result.get("success"):
        logger.warning("Instagram influencer search failed: %s", result.get("error"))
        return []

    influencers: list[dict] = []
    for item in result.get("influencers") or []:
        username = (item.get("username") or "").strip().lstrip("@").lower()
        if not username:
            continue
        influencers.append(
            {
                "username": username,
                "name": item.get("name"),
                "country": item.get("country"),
                "followers": item.get("followers"),
                "category": item.get("category") or [],
                "bio": item.get("bio"),
                "profile_url": item.get("profile_url"),
                "source": item.get("source") or "instagram_search",
                "discovered_by": item.get("discovered_by"),
            }
        )
    return influencers[:limit]


async def fetch_seed_influencers(
    *,
    country: str | None = None,
    categories: list[str] | None = None,
    limit: int = 20,
    seed_usernames: list[str] | None = None,
    auto_discover: bool = True,
    use_database: bool = False,
) -> tuple[list[str], list[dict], str]:
    del use_database
    seed_usernames = normalize_instagram_usernames(seed_usernames)
    normalized_categories = normalize_categories(categories)

    if seed_usernames:
        influencers = [
            {
                "username": (username or "").strip().lstrip("@").lower(),
                "source": "seed_usernames",
                "category": normalized_categories,
            }
            for username in seed_usernames
            if username and str(username).strip()
        ][:limit]
        usernames = [item["username"] for item in influencers]
        return usernames, influencers, "seed_usernames"

    if auto_discover:
        influencers = await discover_influencers_via_instagram(
            country=country,
            categories=normalized_categories or None,
            limit=limit,
        )
        if influencers:
            usernames = [item["username"] for item in influencers]
            return usernames, influencers, "instagram_search"

    return [], [], "none"
