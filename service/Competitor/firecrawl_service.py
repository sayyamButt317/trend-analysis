import logging
from typing import Any
from urllib.parse import urlparse

from config.credential_config import config
from core.api_call_counter import record_api_call

logger = logging.getLogger(__name__)

# Social / non-company hosts — never send these to Firecrawl as "websites".
_BLOCKED_SCRAPE_HOSTS = frozenset(
    {
        "facebook.com",
        "fb.com",
        "fb.me",
        "instagram.com",
        "linkedin.com",
        "twitter.com",
        "x.com",
        "youtube.com",
        "youtu.be",
        "tiktok.com",
        "reddit.com",
        "pinterest.com",
        "threads.net",
    }
)


def is_scrapeable_website(url: str | None) -> bool:
    """Return True only for http(s) company-style URLs (not social profiles)."""
    text = (url or "").strip()
    if not text:
        return False
    if not text.startswith(("http://", "https://")):
        text = f"https://{text.lstrip('/')}"
    try:
        parsed = urlparse(text)
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.netloc or "").lower().removeprefix("www.")
    if not host or "." not in host:
        return False
    if host in _BLOCKED_SCRAPE_HOSTS:
        return False
    if any(host.endswith(f".{blocked}") for blocked in _BLOCKED_SCRAPE_HOSTS):
        return False
    return True


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
        if not is_scrapeable_website(url):
            logger.info("Firecrawl scrape skipped — not a company website: %s", url)
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
            markdown = getattr(result, "markdown", None) or ""
            links = getattr(result, "links", None) or []
            metadata = getattr(result, "metadata", None) or {}
            if markdown or links:
                return {
                    "url": url,
                    "markdown": markdown if isinstance(markdown, str) else "",
                    "links": links if isinstance(links, list) else [],
                    "metadata": metadata if isinstance(metadata, dict) else {},
                }
        except Exception as exc:
            logger.warning("Firecrawl scrape failed for %s: %s", url, exc)
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
        except Exception as exc:
            logger.warning("Firecrawl search failed for query=%s: %s", query, exc)
        return []
