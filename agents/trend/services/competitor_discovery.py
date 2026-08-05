import logging
import re
from typing import Any
from tavily import TavilyClient
from agents.trend.services.competitor_intelligence import (
    CompetitorIntel,
    build_competitor_intelligence,
)
from agents.trend.services.company_profile_parser import CompanySignals, parse_company_profile
from config.credential_config import config
from scrapper.finder_tavily_search import run_limited_searches
from scrapper.tavily_retry import tavily_search_with_retry
from scrapper.instagram_finder.extractor import extract_username
from scrapper.instagram_finder.validator import is_valid_instagram_username

logger = logging.getLogger(__name__)

PLACEHOLDER_USERNAMES = frozenset(
    {"string", "username", "handle", "example", "test", "null", "none"}
)

REGION_ALIASES: dict[str, str] = {
    "gcc": "GCC",
    "gulf": "GCC",
    "middle east": "Middle East",
    "mena": "MENA",
    "europe": "Europe",
    "asia": "Asia",
    "north america": "North America",
    "usa": "United States",
    "us": "United States",
    "uk": "United Kingdom",
    "africa": "Africa",
    "pk": "Pakistan",
    "pakistan": "Pakistan",
    "south asia": "South Asia",
    "global": "Global",
}

GCC_CITIES = ("Dubai", "Abu Dhabi", "Riyadh", "Jeddah", "Doha", "Kuwait City", "Muscat", "Manama")
MENA_CITIES = ("Cairo", "Amman", "Beirut", "Casablanca")
PK_CITIES = ("Lahore", "Karachi", "Islamabad", "Rawalpindi")

# Longest-first so "Limited" wins over "Ltd" style matches when checking endswith.
COMPANY_SUFFIXES = (
    " Private Limited",
    " Pvt. Ltd.",
    " Pvt Ltd",
    " Pvt. Ltd",
    " Corporation",
    " Limited",
    " L.L.C.",
    " LLC",
    " Ltd.",
    " Ltd",
    " Inc.",
    " Inc",
    " Corp.",
    " Corp",
    " Co.",
    " Co",
    " PLC",
)


def _expansion_cities(region: str | None, city: str | None) -> list[str]:
    cities: list[str] = []
    if city:
        cities.append(city.strip())
    if not region:
        return cities
    key = region.lower().strip()
    if key in {"gcc", "gulf", "uae", "united arab emirates", "saudi arabia", "sa", "mena"}:
        cities.extend(GCC_CITIES)
    if key in {"mena", "middle east"}:
        cities.extend(MENA_CITIES)
    if key in {"pakistan", "pk"}:
        cities.extend(PK_CITIES)
    return list(dict.fromkeys(item for item in cities if item))


def _build_expansion_queries(
    *,
    intel: CompetitorIntel,
    location: str,
    services: list[str],
    region: str | None,
    city: str | None,
    round_index: int,
) -> tuple[list[str], list[str]]:
    web: list[str] = []
    instagram: list[str] = []
    service_terms = list(dict.fromkeys([*(services or []), *(intel.target_keywords or [])[:8]]))

    for service in service_terms[:6]:
        web.append(f"{service} companies {location}")
        web.append(f"top {service} agency {location}")
        instagram.append(f"{service} company {location} instagram")
        instagram.append(f"{service} software house {location} site:instagram.com")

    for expansion_city in _expansion_cities(region, city)[:6]:
        for service in service_terms[:3]:
            instagram.append(f"{service} {expansion_city} instagram business")
            web.append(f"{service} company {expansion_city}")

    if round_index >= 2:
        for comp_type in intel.competitor_types[:5]:
            web.append(f"{comp_type} {location}")
            instagram.append(f"{comp_type} {location} instagram")

    return list(dict.fromkeys(web))[:10], list(dict.fromkeys(instagram))[:12]


def normalize_region(region: str | None) -> str | None:
    if not region:
        return None
    text = region.strip()
    if not text:
        return None
    return REGION_ALIASES.get(text.lower(), text)


def build_location_label(
    *,
    region: str | None = None,
    country: str | None = None,
    city: str | None = None,
) -> str:
    parts: list[str] = []
    if city:
        parts.append(city.strip())
    if country:
        parts.append(country.strip())
    if region:
        parts.append(normalize_region(region) or region.strip())
    return " ".join(dict.fromkeys(parts))


def _short_company_name(company_name: str) -> str:
    name = (company_name or "").strip()
    lowered = name.lower()
    for suffix in COMPANY_SUFFIXES:
        if lowered.endswith(suffix.lower()):
            return name[: -len(suffix)].strip(" ,.-")
    return name


def _extract_company_names_from_results(results: list[dict]) -> list[str]:
    names: list[str] = []
    for result in results:
        title = (result.get("title") or "").strip()
        content = (result.get("content") or "").strip()
        for text in (title, content[:200]):
            cleaned = re.sub(r"\s*\|\s*.*$", "", text)
            cleaned = re.sub(r"\s*-\s*.*?(LinkedIn|Instagram|Facebook).*$", "", cleaned, flags=re.I)
            cleaned = cleaned.strip(" -|,")
            if 3 <= len(cleaned) <= 80 and not cleaned.lower().startswith("top "):
                names.append(cleaned)
    return list(dict.fromkeys(names))[:3]


def _search_web_sync(client: TavilyClient, query: str, *, max_results: int = 8) -> list[dict]:
    response = tavily_search_with_retry(
        client,
        query=query,
        search_depth="basic",
        topic="general",
        max_results=max_results,
        include_answer=False,
        include_raw_content=False,
        include_images=False,
    )
    if not response:
        return []
    return response.get("results") or []


def _search_instagram_profiles_sync(
    client: TavilyClient,
    query: str,
    *,
    max_results: int = 8,
) -> list[str]:
    response = tavily_search_with_retry(
        client,
        query=f'site:instagram.com "{query}"',
        search_depth="basic",
        topic="general",
        max_results=max_results,
        include_answer=False,
        include_raw_content=False,
        include_images=False,
    )
    if not response:
        return []

    urls: list[str] = []
    for result in response.get("results") or []:
        url = result.get("url") or ""
        username = extract_username(url)
        if username:
            urls.append(f"https://www.instagram.com/{username}/")
    return list(dict.fromkeys(urls))


def _add_candidate(
    candidates: dict[str, dict],
    username: str,
    *,
    source: str,
    discovered_by: str,
    region: str | None,
    country: str | None,
    city: str | None,
    industry: str | None,
) -> None:
    handle = (username or "").strip().lstrip("@").lower()
    if not handle or not is_valid_instagram_username(handle):
        return
    if handle in candidates:
        existing = candidates[handle]
        if source == "web_company" and existing.get("source") != "web_company":
            existing["source"] = source
        return
    candidates[handle] = {
        "username": handle,
        "profile_url": f"https://www.instagram.com/{handle}/",
        "source": source,
        "discovered_by": discovered_by,
        "region": region,
        "country": country,
        "city": city,
        "industry": industry,
    }


def _company_name_tokens(company_name: str) -> set[str]:
    short = _short_company_name(company_name).lower()
    tokens: set[str] = set()
    if short:
        tokens.add(short.replace(" ", ""))
    alnum = re.sub(r"[^a-z0-9]", "", short)
    if len(alnum) >= 4:
        tokens.add(alnum)
    for part in re.split(r"[\s._-]+", short):
        if len(part) >= 4:
            tokens.add(part)
    return tokens


def _website_stem(website: str | None) -> str | None:
    if not website:
        return None
    match = re.search(r"https?://(?:www\.)?([a-z0-9-]+)\.", website.lower())
    return match.group(1) if match else None


def build_exclude_handles(
    *,
    company_name: str,
    company_username: str | None = None,
    website: str | None = None,
    extra: list[str] | None = None,
) -> set[str]:
    exclude = {
        (company_username or "").strip().lstrip("@").lower(),
        _short_company_name(company_name).lower(),
        *(extra or []),
        *PLACEHOLDER_USERNAMES,
    }
    exclude.discard("")
    return exclude


def is_own_company_account(
    username: str,
    *,
    company_name: str,
    company_username: str | None = None,
    website: str | None = None,
) -> bool:
    handle = (username or "").strip().lstrip("@").lower()
    if not handle:
        return False
    if handle in build_exclude_handles(
        company_name=company_name,
        company_username=company_username,
        website=website,
    ):
        return True

    name_tokens = _company_name_tokens(company_name)
    website_stem = _website_stem(website)
    if website_stem and len(website_stem) >= 4 and website_stem in handle:
        return True

    for token in name_tokens:
        if len(token) >= 5 and token in handle:
            return True
    return False


async def _collect_candidates_from_searches(
    *,
    client: TavilyClient,
    candidate_pool: dict[str, dict],
    web_queries: list[str],
    instagram_queries: list[str],
    normalized_region: str | None,
    country: str | None,
    city: str | None,
    industry: str | None,
    location: str,
) -> None:
    web_fn = lambda query: _search_web_sync(client, query, max_results=10)
    web_results = await run_limited_searches(web_queries, web_fn, concurrency=4)

    for query, results in web_results.items():
        for result in results:
            url = result.get("url") or ""
            username = extract_username(url)
            if username:
                _add_candidate(
                    candidate_pool,
                    username,
                    source="web_search",
                    discovered_by=query,
                    region=normalized_region,
                    country=country,
                    city=city,
                    industry=industry,
                )

        for company in _extract_company_names_from_results(results):
            ig_urls = _search_instagram_profiles_sync(
                client,
                f"{company} {location} instagram".strip(),
                max_results=6,
            )
            for url in ig_urls:
                username = extract_username(url) or ""
                _add_candidate(
                    candidate_pool,
                    username,
                    source="web_company",
                    discovered_by=f"{query} -> {company}",
                    region=normalized_region,
                    country=country,
                    city=city,
                    industry=industry,
                )

    ig_fn = lambda query: _search_instagram_profiles_sync(client, query, max_results=10)
    ig_results = await run_limited_searches(instagram_queries, ig_fn, concurrency=4)
    for query, urls in ig_results.items():
        for url in urls:
            username = extract_username(url) or ""
            _add_candidate(
                candidate_pool,
                username,
                source="instagram_search",
                discovered_by=query,
                region=normalized_region,
                country=country,
                city=city,
                industry=industry,
            )


async def discover_competitors(
    *,
    company_name: str,
    industry: str | None = None,
    category: str | None = None,
    region: str | None = None,
    country: str | None = None,
    city: str | None = None,
    keywords: list[str] | None = None,
    company_description: str | None = None,
    company_profile: str | None = None,
    company_signals: dict[str, Any] | None = None,
    company_username: str | None = None,
    company_website: str | None = None,
    exclude_usernames: list[str] | None = None,
    limit: int = 10,
    pool_size: int | None = None,
) -> tuple[list[dict], dict[str, Any]]:
    normalized_region = normalize_region(region)
    location = build_location_label(region=region, country=country, city=city)
    target_pool = pool_size or max(limit * 2, 40)

    intel = await build_competitor_intelligence(
        company_name=company_name,
        region=region or "Global",
        company_profile=company_profile or company_description or "",
        company_signals=company_signals,
    )

    signals = company_signals or {}
    services = list(
        dict.fromkeys(
            [
                *(intel.target_keywords or [])[:8],
                *(signals.get("flagship_services") or []),
                *(signals.get("services") or []),
                industry or "",
                category or "",
            ]
        )
    )
    services = [item for item in services if item]

    filters_applied = {
        "region": normalized_region,
        "country": country,
        "city": city,
        "industry": industry,
        "category": category,
        "keywords": keywords or [],
        "competitor_limit": limit,
        "competitor_pool_target": target_pool,
        "company_signals": company_signals or {},
        "competitor_intelligence": intel.to_dict(),
        "matching_mode": "smart",
    }

    if not config.TRAVILY_API_KEY:
        logger.warning("TRAVILY_API_KEY is not configured; competitor discovery disabled")
        return [], filters_applied

    client = TavilyClient(api_key=config.TRAVILY_API_KEY)
    candidate_pool: dict[str, dict] = {}

    web_queries = intel.search_queries[:12]
    instagram_queries = intel.instagram_queries[:15]

    await _collect_candidates_from_searches(
        client=client,
        candidate_pool=candidate_pool,
        web_queries=web_queries,
        instagram_queries=instagram_queries,
        normalized_region=normalized_region,
        country=country,
        city=city,
        industry=industry,
        location=location,
    )

    round_index = 1
    while len(candidate_pool) < target_pool and round_index < 2:
        round_index += 1
        extra_web, extra_ig = _build_expansion_queries(
            intel=intel,
            location=location,
            services=services,
            region=region,
            city=city,
            round_index=round_index,
        )
        if not extra_web and not extra_ig:
            break
        logger.info(
            "Competitor discovery expansion round %s (pool=%s target=%s)",
            round_index,
            len(candidate_pool),
            target_pool,
        )
        await _collect_candidates_from_searches(
            client=client,
            candidate_pool=candidate_pool,
            web_queries=extra_web,
            instagram_queries=extra_ig,
            normalized_region=normalized_region,
            country=country,
            city=city,
            industry=industry,
            location=location,
        )

    exclude = build_exclude_handles(
        company_name=company_name,
        company_username=company_username,
        website=company_website,
        extra=[*(exclude_usernames or [])],
    )

    candidates = [
        item
        for handle, item in candidate_pool.items()
        if handle not in exclude
        and not is_own_company_account(
            handle,
            company_name=company_name,
            company_username=company_username,
            website=company_website,
        )
    ]

    filters_applied["search_queries"] = {
        "web_queries": web_queries,
        "instagram_queries": instagram_queries,
        "expansion_rounds": round_index - 1,
    }
    filters_applied["candidate_pool_size"] = len(candidates)

    logger.info(
        "Smart discovery found %s Instagram candidate(s) for company=%s location=%s (intel=%s pool_target=%s)",
        len(candidates),
        company_name,
        location or "global",
        intel.source,
        target_pool,
    )

    return candidates, filters_applied
