import logging
from typing import Any
from config.credential_config import config
from core.api_call_counter import record_api_call

logger = logging.getLogger(__name__)


class FirecrawlService:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (api_key or config.FIRECRAWL_API_KEY or "").strip()
        self._client = None

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is None:
            from firecrawl import FirecrawlApp

            self._client = FirecrawlApp(api_key=self.api_key)
        return self._client

    def scrape_url(self, url: str) -> dict[str, Any]:
        if not self.available:
            logger.warning("FIRECRAWL_API_KEY not configured")
            return {}
        try:
            client = self._get_client()
            record_api_call("firecrawl", kind="scrape")
            result = client.scrape(url, formats=["markdown", "links"])
            if isinstance(result, dict):
                data = result.get("data") or result
                return {
                    "url": url,
                    "markdown": data.get("markdown") or "",
                    "links": data.get("links") or [],
                    "metadata": data.get("metadata") or {},
                }
        except Exception:
            logger.exception("Firecrawl scrape failed for %s", url)
        return {}

    def search_web(self, query: str, *, limit: int = 8) -> list[dict[str, Any]]:
        if not self.available:
            return []
        try:
            client = self._get_client()
            record_api_call("firecrawl", kind="search")
            response = client.search(query, limit=limit)
            if isinstance(response, dict):
                return response.get("data") or response.get("results") or []
            if isinstance(response, list):
                return response
        except Exception:
            logger.exception("Firecrawl search failed for query=%s", query)
        return []
