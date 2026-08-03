import logging
from tavily import TavilyClient
from config.credential_config import config
from scrapper.instagram_finder.extractor import extract_username
from scrapper.instagram_finder.validator import is_valid_instagram_username
from scrapper.tavily_retry import tavily_search_with_retry

logger = logging.getLogger(__name__)


def normalize_competitor_inputs(values: list[str] | None) -> list[str]:
    if not values:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = (value or "").strip()
        if not text:
            continue
        key = text.lower().lstrip("@")
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def _is_instagram_handle(value: str) -> bool:
    handle = value.strip().lstrip("@").lower()
    return bool(handle) and is_valid_instagram_username(handle)


def _search_instagram_for_name_sync(client: TavilyClient, query: str) -> str | None:
    response = tavily_search_with_retry(
        client,
        query=f'site:instagram.com "{query}"',
        search_depth="basic",
        topic="general",
        max_results=5,
        include_answer=False,
        include_raw_content=False,
        include_images=False,
    )
    if not response:
        return None
    for result in response.get("results") or []:
        username = extract_username(result.get("url") or "")
        if username and is_valid_instagram_username(username):
            return username.lower()
    return None


async def resolve_manual_competitors(
    competitors: list[str],
    *,
    region: str | None = None,
) -> tuple[list[dict], list[str]]:
    inputs = normalize_competitor_inputs(competitors)
    if not inputs:
        return [], []

    warnings: list[str] = []
    candidates: list[dict] = []
    seen_handles: set[str] = set()
    names_to_search: list[str] = []

    for item in inputs:
        if _is_instagram_handle(item):
            handle = item.strip().lstrip("@").lower()
            if handle in seen_handles:
                continue
            seen_handles.add(handle)
            candidates.append(
                {
                    "username": handle,
                    "name": item.strip().lstrip("@"),
                    "profile_url": f"https://www.instagram.com/{handle}/",
                    "source": "manual",
                    "discovered_by": "user_provided_handle",
                    "match_score": 1.0,
                    "match_reasons": ["User-provided competitor handle"],
                }
            )
        else:
            names_to_search.append(item)

    if names_to_search:
        if not config.TRAVILY_API_KEY:
            warnings.append(
                "TRAVILY_API_KEY is not configured; company names could not be resolved to "
                "Instagram handles. Provide @handles instead."
            )
        else:
            client = TavilyClient(api_key=config.TRAVILY_API_KEY)
            location_suffix = f" {region}".strip() if region else ""
            for name in names_to_search:
                query = f"{name}{location_suffix} instagram".strip()
                handle = _search_instagram_for_name_sync(client, query)
                if not handle:
                    warnings.append(f"Could not find Instagram account for '{name}'.")
                    continue
                if handle in seen_handles:
                    continue
                seen_handles.add(handle)
                candidates.append(
                    {
                        "username": handle,
                        "name": name,
                        "profile_url": f"https://www.instagram.com/{handle}/",
                        "source": "manual",
                        "discovered_by": f"user_provided_name: {name}",
                        "match_score": 1.0,
                        "match_reasons": [f"Resolved from user-provided name: {name}"],
                    }
                )

    logger.info(
        "Manual competitor resolution: %s input(s) -> %s Instagram account(s)",
        len(inputs),
        len(candidates),
    )
    return candidates, warnings
