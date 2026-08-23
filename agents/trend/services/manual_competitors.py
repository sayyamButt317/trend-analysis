"""Resolve user-provided competitors: Instagram handles, LinkedIn URLs, website URLs, or company names."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

from tavily import TavilyClient

from config.credential_config import config
from scrapper.instagram_finder.extractor import extract_username
from scrapper.instagram_finder.validator import is_valid_instagram_username
from scrapper.tavily_retry import is_tavily_unreachable_error, tavily_search_with_retry
from service.Competitor.firecrawl_service import is_scrapeable_website

logger = logging.getLogger(__name__)

LINKEDIN_COMPANY_RE = re.compile(
    r"(?:https?://)?(?:[\w.-]+\.)?linkedin\.com/company/([A-Za-z0-9\-_%]+)/?",
    re.I,
)
INSTAGRAM_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9._]+)/?",
    re.I,
)


def normalize_competitor_inputs(values: list[str] | None) -> list[str]:
    if not values:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = (value or "").strip()
        if not text:
            continue
        key = text.lower().rstrip("/").lstrip("@")
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def _instagram_handle_from_input(value: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    url_match = INSTAGRAM_URL_RE.search(text)
    if url_match:
        handle = url_match.group(1).lower()
        if handle in {"p", "reel", "reels", "stories", "explore", "accounts"}:
            return None
        return handle if is_valid_instagram_username(handle) else None

    # Explicit @handle
    if text.startswith("@"):
        handle = text.lstrip("@").strip().lower()
        return handle if is_valid_instagram_username(handle) else None

    # Company names often have spaces or internal capitals (VentureDive).
    if " " in text or any(ch.isupper() for ch in text[1:]):
        return None
    if "linkedin.com" in text.lower() or "/" in text:
        return None

    handle = text.strip().lower()
    return handle if is_valid_instagram_username(handle) else None


def _linkedin_url_from_input(value: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    match = LINKEDIN_COMPANY_RE.search(text)
    if not match:
        return None
    slug = match.group(1).strip("/")
    return f"https://www.linkedin.com/company/{slug}/"


def _website_url_from_input(value: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if text.startswith("@"):
        return None
    if "linkedin.com" in text.lower() or "instagram.com" in text.lower():
        return None
    if not text.startswith(("http://", "https://")):
        head = text.split("/")[0].strip()
        if "." not in head:
            return None
        text = f"https://{text.lstrip('/')}"
    if not is_scrapeable_website(text):
        return None
    parsed = urlparse(text)
    if parsed.path in {"", "/"} and not parsed.query:
        return f"{parsed.scheme}://{parsed.netloc}".lower()
    return text.rstrip("/")


def _company_name_from_website(url: str) -> str:
    host = (urlparse(url).netloc or "").lower().removeprefix("www.")
    label = host.split(".")[0] if host else "Competitor"
    cleaned = re.sub(r"[^a-z0-9]+", " ", label, flags=re.I).strip()
    return cleaned.title() if cleaned else "Competitor"


def _company_name_from_input(value: str, *, ig: str | None, linkedin: str | None) -> str:
    text = (value or "").strip()
    if ig and (text.lower().lstrip("@") == ig or "instagram.com" in text.lower()):
        return ig
    if linkedin:
        match = LINKEDIN_COMPANY_RE.search(text)
        if match:
            slug = match.group(1).replace("-", " ").replace("_", " ").strip()
            return slug.title() if slug else text
    return text.lstrip("@").strip() or "Competitor"


def _search_instagram_for_name_sync(
    client: TavilyClient,
    query: str,
) -> str | None:
    response = tavily_search_with_retry(
        client,
        query=f'site:instagram.com "{query}"',
        search_depth="basic",
        topic="general",
        max_results=5,
        include_answer=False,
        include_raw_content=False,
        include_images=False,
        count_as_linkedin=False,
    )
    if not response:
        return None
    for result in response.get("results") or []:
        username = extract_username(result.get("url") or "")
        if username and is_valid_instagram_username(username):
            return username.lower()
    return None


def _search_linkedin_for_name_sync(
    client: TavilyClient,
    query: str,
) -> str | None:
    response = tavily_search_with_retry(
        client,
        query=f'site:linkedin.com/company "{query}"',
        search_depth="basic",
        topic="general",
        max_results=5,
        include_answer=False,
        include_raw_content=False,
        include_images=False,
        count_as_linkedin=True,
    )
    if not response:
        return None
    for result in response.get("results") or []:
        url = result.get("url") or ""
        match = LINKEDIN_COMPANY_RE.search(url)
        if match:
            return f"https://www.linkedin.com/company/{match.group(1).strip('/')}/"
    return None


def _candidate_payload(
    *,
    name: str,
    username: str | None = None,
    linkedin_url: str | None = None,
    website: str | None = None,
    discovered_by: str,
    raw_input: str,
) -> dict[str, Any]:
    socials: dict[str, str] = {}
    if username:
        socials["instagram"] = username
    if linkedin_url:
        socials["linkedin"] = linkedin_url
    return {
        "name": name,
        "username": username,
        "instagram_username": username,
        "linkedin_url": linkedin_url,
        "website": website,
        "profile_url": f"https://www.instagram.com/{username}/" if username else None,
        "socials": socials,
        "source": "manual",
        "authenticity": "manual",
        "discovery_source": "manual",
        "discovered_by": discovered_by,
        "raw_input": raw_input,
        "match_score": 1.0,
        "match_reasons": [f"User-provided competitor ({discovered_by})"],
        "region_match": True,
        "niche_match": True,
    }


async def resolve_manual_competitors(
    competitors: list[str],
    *,
    region: str | None = None,
) -> tuple[list[dict], list[str]]:
    """
    Resolve tenant-provided competitors.

    Accepted input forms (mixed list OK):
    - Instagram handle: "@confiz" or "confiz" or instagram.com/confiz
    - LinkedIn company URL: https://www.linkedin.com/company/confiz/
    - Company website URL: https://confiz.com or confiz.com
    - Company name only: "Confiz" (resolved via Tavily to IG and/or LinkedIn)
    """
    inputs = normalize_competitor_inputs(competitors)
    if not inputs:
        return [], []

    warnings: list[str] = []
    candidates: list[dict] = []
    seen_keys: set[str] = set()
    needs_lookup: list[tuple[str, dict[str, Any]]] = []

    for item in inputs:
        ig = _instagram_handle_from_input(item)
        linkedin = _linkedin_url_from_input(item)
        website = _website_url_from_input(item) if not ig and not linkedin else None
        name = _company_name_from_input(item, ig=ig, linkedin=linkedin)
        if website and not ig and not linkedin:
            name = _company_name_from_website(website)

        # Pure handle, LinkedIn URL, or website URL — accept immediately.
        if ig or linkedin or website:
            key = (
                (ig or "")
                or (linkedin or "").rstrip("/").lower()
                or (website or "").rstrip("/").lower()
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            discovered = (
                "user_provided_handle"
                if ig and not linkedin and not website
                else "user_provided_linkedin"
                if linkedin and not ig and not website
                else "user_provided_website"
                if website and not ig and not linkedin
                else "user_provided_socials"
            )
            candidates.append(
                _candidate_payload(
                    name=name,
                    username=ig,
                    linkedin_url=linkedin,
                    website=website,
                    discovered_by=discovered,
                    raw_input=item,
                )
            )
            continue

        # Company name — may need Tavily to fill IG/LinkedIn.
        needs_lookup.append((item, {"name": name}))

    if needs_lookup:
        api_key = (config.TRAVILY_API_KEY or "").strip()
        if not api_key:
            for raw, meta in needs_lookup:
                # Keep name-only peers so LinkedIn analysis can still run after later fill.
                key = meta["name"].lower()
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                candidates.append(
                    _candidate_payload(
                        name=meta["name"],
                        discovered_by="user_provided_name",
                        raw_input=raw,
                    )
                )
            warnings.append(
                "TRAVILY_API_KEY missing — kept company names without resolving Instagram/LinkedIn."
            )
        else:
            client = TavilyClient(api_key=api_key)
            location_suffix = f" {region}".strip() if region else ""
            for raw, meta in needs_lookup:
                name = meta["name"]
                handle: str | None = None
                linkedin_url: str | None = None
                try:
                    handle = _search_instagram_for_name_sync(
                        client, f"{name}{location_suffix}".strip()
                    )
                    linkedin_url = _search_linkedin_for_name_sync(
                        client, f"{name}{location_suffix}".strip()
                    )
                except Exception as exc:
                    if not is_tavily_unreachable_error(exc):
                        logger.warning("Manual competitor lookup failed for %s: %s", name, exc)
                    warnings.append(f"Lookup failed for '{name}': {exc}")

                key = (handle or "") or (linkedin_url or "").rstrip("/").lower() or name.lower()
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                if not handle and not linkedin_url:
                    warnings.append(
                        f"Could not resolve Instagram/LinkedIn for '{name}'; keeping name for analysis."
                    )
                candidates.append(
                    _candidate_payload(
                        name=name,
                        username=handle,
                        linkedin_url=linkedin_url,
                        discovered_by=f"user_provided_name: {name}",
                        raw_input=raw,
                    )
                )

    # Drop empty shells with no identity at all.
    usable = [
        c
        for c in candidates
        if c.get("username") or c.get("linkedin_url") or c.get("website") or c.get("name")
    ]

    logger.info(
        "Manual competitor resolution: %s input(s) -> %s competitor(s) "
        "(ig=%s linkedin=%s website=%s name_only=%s)",
        len(inputs),
        len(usable),
        sum(1 for c in usable if c.get("username")),
        sum(1 for c in usable if c.get("linkedin_url")),
        sum(1 for c in usable if c.get("website")),
        sum(
            1
            for c in usable
            if not c.get("username") and not c.get("linkedin_url") and not c.get("website")
        ),
    )
    return usable, warnings
