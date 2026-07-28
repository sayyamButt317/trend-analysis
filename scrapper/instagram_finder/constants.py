GCC_SEARCH_TERMS: dict[str, list[str]] = {
    "United Arab Emirates": [
        "Dubai influencer",
        "Abu Dhabi influencer",
        "Sharjah influencer",
        "UAE blogger",
        "UAE fashion influencer",
        "UAE lifestyle influencer",
        "Dubai travel influencer",
        "Dubai fitness influencer",
        "Dubai makeup artist",
        "Dubai food blogger",
        "Dubai luxury influencer",
        "Emirati influencer",
    ],
    "Saudi Arabia": [
        "Saudi influencer",
        "Saudi blogger",
        "Riyadh influencer",
        "Jeddah influencer",
        "Saudi fashion influencer",
        "Saudi beauty influencer",
        "Saudi fitness influencer",
        "Saudi lifestyle influencer",
        "Khobar influencer",
        "Saudi food blogger",
    ],
}

SUPPORTED_COUNTRIES = tuple(GCC_SEARCH_TERMS.keys())
SUPPORTED_CATEGORIES = (
    "Fashion",
    "Beauty",
    "Fitness",
    "Food",
    "Travel",
    "Luxury",
    "Lifestyle",
)
DEFAULT_MAX_RESULTS_PER_QUERY = 10


def normalize_categories(categories: list[str] | str | None) -> list[str]:
    if not categories:
        return []
    items = [categories] if isinstance(categories, str) else list(categories)
    normalized: list[str] = []
    supported = {item.lower(): item for item in SUPPORTED_CATEGORIES}
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        canonical = supported.get(text.lower())
        if canonical and canonical not in normalized:
            normalized.append(canonical)
    return normalized


def filter_search_terms_by_categories(
    terms: list[str],
    categories: list[str] | None,
    *,
    country: str | None = None,
) -> list[str]:
    if not categories:
        return terms



    targets = {category.lower() for category in categories}
    from scrapper.instagram_finder.enricher import category_from_search_term

    filtered = [
        term
        for term in terms
        if any(
            matched.lower() in targets
            for matched in category_from_search_term(term)
        )
    ]
    if filtered:
        return filtered

    prefix_by_country = {
        "United Arab Emirates": "UAE",
        "Saudi Arabia": "Saudi",
    }
    prefix = prefix_by_country.get(country or "", country or "")
    return [f"{prefix} {category} influencer".strip() for category in categories]


def influencer_matches_categories(
    influencer_categories: list[str] | None,
    categories: list[str] | None,
) -> bool:
    if not categories:
        return True
    targets = {category.lower() for category in categories}
    for category in influencer_categories or []:
        if str(category).lower() in targets:
            return True
    return False

RESERVED_INSTAGRAM_PATHS = frozenset(
    {
        "p",
        "reel",
        "reels",
        "tv",
        "explore",
        "stories",
        "accounts",
        "about",
        "legal",
        "developer",
        "privacy",
        "terms",
        "api",
        "web",
        "direct",
        "challenge",
        "directory",
        "nametag",
        "popular",
    }
)
