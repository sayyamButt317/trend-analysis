import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

from config.credential_config import config
from models.search import DiscoveryCandidate
from scrapper.tavily_retry import tavily_search_with_retry

logger = logging.getLogger(__name__)

BLOCKED_DOMAINS = frozenset(
    {
        "linkedin.com",
        "facebook.com",
        "instagram.com",
        "twitter.com",
        "x.com",
        "youtube.com",
        "reddit.com",
        "wikipedia.org",
        "indeed.com",
        "glassdoor.com",
    }
)


class TavilyDiscoveryService:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (api_key or config.TRAVILY_API_KEY or "").strip()

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str) -> list[dict[str, Any]]:
        if not self.available:
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
            return (response or {}).get("results") or []
        except Exception:
            logger.exception("Tavily failed %s", query)
            return []

    async def discover(self, queries: list[str]) -> list[DiscoveryCandidate]:
        if not queries:
            return []
        tasks = [self.search(query) for query in queries[:20]]
        results = await asyncio.gather(*tasks)
        candidates: list[DiscoveryCandidate] = []
        seen_urls: set[str] = set()
        for query, items in zip(queries[:20], results):
            for item in items:
                url = (item.get("url") or "").strip()
                if not url or url in seen_urls:
                    continue
                domain = urlparse(url).netloc.lower().replace("www.", "")
                if any(blocked in domain for blocked in BLOCKED_DOMAINS):
                    continue
                seen_urls.add(url)
                candidates.append(
                    DiscoveryCandidate(
                        company_name=(item.get("title") or "").strip()[:120],
                        website=url,
                        description=(item.get("content") or "")[:500],
                        source_query=query,
                        tavily_score=float(item.get("score") or 0),
                        title=(item.get("title") or "")[:120],
                    )
                )
        return candidates
