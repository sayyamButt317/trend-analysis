from scrapper.instagram_finder.constants import (
    SUPPORTED_COUNTRIES,
    influencer_matches_categories,
    normalize_categories,
)
from scrapper.instagram_finder.country_detector import (
    country_from_search_term,
    normalize_target_countries,
)
from scrapper.instagram_finder.database import mark_existing_users
from scrapper.instagram_finder.enricher import (
    category_from_search_term,
    enrich_instagram_users,
)
from scrapper.instagram_finder.extractor import extract_username
from scrapper.instagram_finder.models import InstagramUser
from scrapper.instagram_finder.search import InstagramSearch
from scrapper.instagram_finder.validator import is_valid_instagram_username


async def find_gcc_influencers(
    *,
    countries: list[str] | None = None,
    categories: list[str] | None = None,
    max_count: int = 20,
    enrich_profiles: bool = True,
    job=None,
) -> dict:
    target_countries = normalize_target_countries(countries)
    target_categories = normalize_categories(categories)
    if not target_countries:
        return {
            "success": False,
            "error": (
                f"Unsupported country. Use one of: {', '.join(SUPPORTED_COUNTRIES)}"
            ),
            "countries": [],
            "total_found": 0,
            "total_new": 0,
            "total_existing": 0,
            "influencers": [],
        }

    if job:
        await job.emit(
            {
                "type": "search_started",
                "countries": target_countries,
                "categories": target_categories,
            }
        )

    search = InstagramSearch(max_results_per_query=max_count)
    search_results = await search.search_by_countries(
        target_countries,
        categories=target_categories or None,
    )

    if job:
        await job.emit(
            {
                "type": "search_completed",
                "countries": target_countries,
                "search_results_count": sum(
                    len(urls)
                    for term_results in search_results.values()
                    for urls in term_results.values()
                ),
            }
        )

    users_by_username: dict[str, InstagramUser] = {}
    for country, term_results in search_results.items():
        for search_term, urls in term_results.items():
            detected_country = country_from_search_term(search_term) or country
            for url in urls:
                username = extract_username(url)
                if not username or not is_valid_instagram_username(username):
                    continue

                handle = username.lower()
                if handle in users_by_username:
                    continue

                users_by_username[handle] = InstagramUser(
                    username=handle,
                    profile_url=f"https://www.instagram.com/{handle}/",
                    country=detected_country,
                    discovered_by=search_term,
                    category=category_from_search_term(search_term),
                )

    influencers = await mark_existing_users(list(users_by_username.values()))

    if job:
        for user in influencers:
            await job.emit(
                {"type": "influencer_found", "influencer": user.to_dict()}
            )

    if enrich_profiles:
        new_users = [user for user in influencers if user.source == "new"]
        if new_users:
            await enrich_instagram_users(new_users, job=job)

    if target_categories:
        influencers = [
            user
            for user in influencers
            if influencer_matches_categories(user.category, target_categories)
        ]

    influencers.sort(
        key=lambda user: (
            -(user.followers or 0),
            0 if user.source == "new" else 1,
            user.country or "",
            user.username,
        )
    )

    total_new = sum(1 for user in influencers if user.source == "new")
    total_existing = len(influencers) - total_new

    return {
        "success": True,
        "countries": target_countries,
        "categories": target_categories,
        "total_found": len(influencers),
        "total_new": total_new,
        "total_existing": total_existing,
        "influencers": [user.to_dict() for user in influencers],
    }
