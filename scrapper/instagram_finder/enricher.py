import asyncio

from scrapper.instagram_finder.models import InstagramUser
from agents.trend.services.instagramuser_details import (
    ExtractInfluencerDetailsFromInstagram,
    InstagramRateLimitError,
)

INSTAGRAM_RATE_LIMIT_MESSAGE = "Instagram API rate limit reached"

CATEGORY_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("fashion",), "Fashion"),
    (("beauty", "makeup"), "Beauty"),
    (("fitness",), "Fitness"),
    (("food",), "Food"),
    (("travel",), "Travel"),
    (("luxury",), "Luxury"),
    (("lifestyle", "blogger"), "Lifestyle"),
)


def category_from_search_term(search_term: str | None) -> list[str]:
    lowered = (search_term or "").lower()
    for keywords, category in CATEGORY_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return [category]
    return ["Influencer"]


async def _fetch_instagram_profile(username: str) -> dict | None:
    try:
        return await ExtractInfluencerDetailsFromInstagram(username)
    except InstagramRateLimitError as exc:
        raise RuntimeError(INSTAGRAM_RATE_LIMIT_MESSAGE) from exc


async def enrich_instagram_users(
    users: list[InstagramUser],
    *,
    max_concurrency: int = 3,
    job=None,
) -> list[InstagramUser]:
    if not users:
        return users

    semaphore = asyncio.Semaphore(max(1, max_concurrency))
    rate_limited = False

    async def enrich_one(user: InstagramUser) -> None:
        nonlocal rate_limited
        if rate_limited:
            return
        if user.followers is not None and user.category:
            if job:
                await job.emit(
                    {"type": "influencer_enriched", "influencer": user.to_dict()}
                )
            return

        async with semaphore:
            if rate_limited:
                return
            try:
                profile = await _fetch_instagram_profile(user.username)
            except RuntimeError as exc:
                if str(exc) == INSTAGRAM_RATE_LIMIT_MESSAGE:
                    rate_limited = True
                    if job:
                        await job.emit(
                            {
                                "type": "error",
                                "error": INSTAGRAM_RATE_LIMIT_MESSAGE,
                            }
                        )
                return
            except Exception:
                return

            if not profile:
                if not user.category:
                    user.category = category_from_search_term(user.discovered_by)
                if job:
                    await job.emit(
                        {"type": "influencer_enriched", "influencer": user.to_dict()}
                    )
                return

            user.name = profile.get("name") or user.name
            user.bio = profile.get("biography") or user.bio
            user.pic = profile.get("profile_picture_url") or user.pic
            user.followers = profile.get("followers_count") or user.followers
            if not user.category:
                user.category = category_from_search_term(user.discovered_by)
            if job:
                await job.emit(
                    {"type": "influencer_enriched", "influencer": user.to_dict()}
                )

    await asyncio.gather(*(enrich_one(user) for user in users))
    return users
