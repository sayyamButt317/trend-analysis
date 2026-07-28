from scrapper.instagram_finder.constants import GCC_SEARCH_TERMS, SUPPORTED_COUNTRIES

UAE_HINTS = (
    "dubai",
    "abu dhabi",
    "sharjah",
    "uae",
    "emirati",
    "emirates",
)

SAUDI_HINTS = (
    "saudi",
    "riyadh",
    "jeddah",
    "khobar",
    "ksa",
)


def country_from_search_term(search_term: str) -> str | None:
    lowered = (search_term or "").lower()
    for country, terms in GCC_SEARCH_TERMS.items():
        if search_term in terms:
            return country

    if any(hint in lowered for hint in UAE_HINTS):
        return "United Arab Emirates"
    if any(hint in lowered for hint in SAUDI_HINTS):
        return "Saudi Arabia"
    return None


def normalize_target_countries(countries: list[str] | None) -> list[str]:
    if not countries:
        return list(SUPPORTED_COUNTRIES)

    normalized: list[str] = []
    for country in countries:
        value = (country or "").strip()
        if not value:
            continue
        lowered = value.lower()
        if lowered in {"uae", "united arab emirates", "emirates"}:
            normalized.append("United Arab Emirates")
        elif lowered in {"saudi", "saudi arabia", "ksa", "kingdom of saudi arabia"}:
            normalized.append("Saudi Arabia")
        elif value in SUPPORTED_COUNTRIES:
            normalized.append(value)

    return list(dict.fromkeys(normalized))
