import asyncio
import logging
import re
from typing import Any
from urllib.parse import urlparse
from config.credential_config import config
from models.search import DiscoveryCandidate
from scrapper.tavily_retry import tavily_search_with_retry

logger = logging.getLogger(__name__)

BLOCKED_DOMAINS = frozenset(
    {
        "facebook.com",
        "twitter.com",
        "x.com",
        "youtube.com",
        "reddit.com",
        "wikipedia.org",
        "indeed.com",
        "glassdoor.com",
    }
)

RESERVED_IG_SEGMENTS = frozenset({"p", "reel", "reels", "stories", "explore", "accounts"})


def _instagram_handle(url: str) -> str | None:
    match = re.search(r"instagram\.com/([A-Za-z0-9._]+)", url, re.I)
    if not match:
        return None
    handle = match.group(1).lower()
    if handle in RESERVED_IG_SEGMENTS:
        return None
    return handle


def _linkedin_company_slug(url: str) -> str | None:
    match = re.search(r"linkedin\.com/company/([^/?#]+)", url, re.I)
    return match.group(1).lower() if match else None


def _candidate_dedupe_key(url: str, company_name: str) -> str:
    ig = _instagram_handle(url)
    if ig:
        return f"ig:{ig}"
    li = _linkedin_company_slug(url)
    if li:
        return f"li:{li}"
    domain = urlparse(url).netloc.lower().replace("www.", "")
    return domain or company_name.lower()


class TavilyDiscoveryService:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (api_key or config.TRAVILY_API_KEY or "").strip()

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str) -> list[dict[str, Any]]:
        if not self.available:
            logger.warning("Tavily search skipped — TRAVILY_API_KEY not configured")
            return []
        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=self.api_key)
            response = tavily_search_with_retry(
                client,
                query=query,
                search_depth="advanced",
                max_results=10,
                include_answer=False,
                include_images=False,
            )
            results = (response or {}).get("results") or []
            logger.info("Tavily returned %s result(s) for query=%r", len(results), query[:80])
            return results
        except Exception:
            logger.exception("Tavily failed %s", query)
            return []

    async def discover(
        self,
        queries: list[str],
        *,
        max_queries: int | None = None,
    ) -> list[DiscoveryCandidate]:
        if not self.available:
            return []
        if not queries:
            return []
        cap = max_queries if max_queries is not None else 10
        capped = queries[:cap]
        tasks = [self.search(query) for query in capped]
        results = await asyncio.gather(*tasks)
        candidates: list[DiscoveryCandidate] = []
        seen_keys: set[str] = set()
        for query, items in zip(capped, results):
            for item in items:
                url = (item.get("url") or "").strip()
                if not url:
                    continue
                title = (item.get("title") or "").strip()[:120]
                dedupe_key = _candidate_dedupe_key(url, title)
                if dedupe_key in seen_keys:
                    continue

                domain = urlparse(url).netloc.lower().replace("www.", "")
                ig_handle = _instagram_handle(url)
                li_slug = _linkedin_company_slug(url)
                social_links: dict[str, str] = {}

                if ig_handle:
                    social_links["instagram"] = url
                elif li_slug:
                    social_links["linkedin"] = url
                elif any(blocked in domain for blocked in BLOCKED_DOMAINS):
                    continue
                elif "instagram.com" in domain or "linkedin.com" in domain:
                    continue

                seen_keys.add(dedupe_key)
                candidates.append(
                    DiscoveryCandidate(
                        company_name=title,
                        website="" if social_links else url,
                        description=(item.get("content") or "")[:500],
                        source_query=query,
                        tavily_score=float(item.get("score") or 0),
                        title=title,
                        social_links=social_links,
                    )
                )
        logger.info(
            "Tavily discover: %s candidate(s) from %s queries",
            len(candidates),
            len(capped),
        )
        return candidates
