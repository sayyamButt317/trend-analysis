import logging
from typing import Any

from agents.competitor.state.competitor_state import CompetitorState
from agents.trend.services.company_social_analyzer import (
    analyze_instagram_company_profile,
    resolve_company_social_handles,
)
from agents.trend.services.instagram_discovery import fetch_instagram_profile
from agents.trend.services.instagramuser_details import InstagramRateLimitError

logger = logging.getLogger(__name__)

Competitor = dict[str, Any]


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


def _posts_from_profile(profile: dict[str, Any], *, handle: str) -> list[dict[str, Any]]:
    followers = int(profile.get("followers_count") or 0)
    media_items = (profile.get("media") or {}).get("data") or profile.get("posts") or []
    posts: list[dict[str, Any]] = []
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
                "normalized_media_type": normalized_media_type,
            }
        )
    return posts


async def analyze_competitor_instagram(
    competitor: Competitor,
    *,
    region: str | None = None,
    post_limit: int = 15,
) -> Competitor:
    """Fetch and analyze a competitor's Instagram presence."""
    username = (competitor.get("username") or "").strip().lstrip("@").lower()
    name = (competitor.get("name") or username or "").strip()
    warnings: list[str] = list(competitor.get("social_warnings") or [])

    if not username and name:
        handles = await resolve_company_social_handles(
            {
                "name": name,
                "website": competitor.get("website"),
                "profile": competitor.get("bio") or "",
            },
            region=region,
        )
        username = (handles.get("instagram_username") or "").strip().lstrip("@").lower()
        if handles.get("instagram_url"):
            competitor["profile_url"] = handles["instagram_url"]

    enriched = dict(competitor)
    if not username:
        warnings.append(f"No Instagram account found for competitor '{name}'.")
        enriched["social_warnings"] = warnings
        enriched["instagram_analysis"] = None
        return enriched

    profile = competitor.get("instagram_profile")
    posts = list(competitor.get("instagram_posts") or [])

    if not profile:
        try:
            profile = await fetch_instagram_profile(username, post_limit=post_limit)
        except InstagramRateLimitError:
            raise
        except Exception:
            logger.warning("Instagram analysis failed for @%s", username, exc_info=True)
            profile = None

    if profile and not posts:
        posts = _posts_from_profile(profile, handle=username)

    if not profile:
        warnings.append(f"Could not fetch Instagram profile for @{username}.")
        enriched.update(
            {
                "username": username,
                "profile_url": enriched.get("profile_url") or f"https://www.instagram.com/{username}/",
                "social_warnings": warnings,
                "instagram_analysis": None,
            }
        )
        return enriched

    if not posts:
        posts = _posts_from_profile(profile, handle=username)
    analysis = analyze_instagram_company_profile(profile, posts)

    enriched.update(
        {
            "username": profile.get("username") or username,
            "name": profile.get("name") or name,
            "bio": profile.get("biography") or profile.get("bio") or competitor.get("bio"),
            "followers": int(profile.get("followers_count") or competitor.get("followers") or 0),
            "website": profile.get("website") or competitor.get("website"),
            "profile_picture_url": profile.get("profile_picture_url"),
            "profile_url": enriched.get("profile_url") or f"https://www.instagram.com/{username}/",
            "instagram_profile": profile,
            "instagram_posts": posts,
            "instagram_analysis": analysis,
            "social_warnings": warnings,
        }
    )
    return enriched


async def analyzeCompetitorInsta(competitor: Competitor) -> Competitor:
    return await analyze_competitor_instagram(competitor)


async def AnalyzeCompetitorInstaNode(state: CompetitorState) -> CompetitorState:
    if state.get("error"):
        return state

    config = state.get("config") or {}
    filters = config.get("filters") or config
    region = filters.get("region") or config.get("region")
    post_limit = int(filters.get("post_limit") or config.get("post_limit") or 15)

    competitors = state.get("discovered_influencers") or state.get("competitors") or []
    enriched: list[Competitor] = []

    for competitor in competitors:
        try:
            item = await analyze_competitor_instagram(
                competitor,
                region=region,
                post_limit=post_limit,
            )
            enriched.append(item)
        except InstagramRateLimitError:
            state["error"] = "Instagram API rate limit reached. Wait a few minutes and retry."
            return state
        except Exception:
            logger.exception(
                "Instagram analysis failed for competitor=%s",
                competitor.get("username") or competitor.get("name"),
            )
            enriched.append({**competitor, "instagram_analysis": None})

    state["discovered_influencers"] = enriched
    state["competitors"] = enriched
    return state
