import asyncio
import logging
import re
from datetime import datetime, timezone
from html import unescape
from typing import Any
import httpx
from agents.trend.services.google_trend_fetcher import fetch_google_trends
from agents.trend.services.web_trend_parser import parse_source_content
from agents.trend.services.web_trend_sources import TAVILY_TREND_QUERIES, TREND_SOURCES
from config.credential_config import config

logger = logging.getLogger(__name__)

STRIP_TAGS_RE = re.compile(r"<[^>]+>")


def _html_to_text(content: str) -> str:
    text = unescape(STRIP_TAGS_RE.sub(" ", content or ""))
    text = re.sub(r"\s+", " ", text)
    return text


async def _fetch_with_httpx(url: str, *, timeout: float = 20.0) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; TrendBot/1.0; +https://github.com/techtimize/trend)"
        ),
        "Accept": "text/html,application/xhtml+xml,text/plain",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return _html_to_text(response.text)


def _fetch_with_tavily_extract(url: str) -> str:
    api_key = (config.TRAVILY_API_KEY or "").strip()
    if not api_key:
        return ""
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        if hasattr(client, "extract"):
            result = client.extract(urls=[url])
            chunks = result.get("results") or []
            if chunks:
                return chunks[0].get("raw_content") or chunks[0].get("content") or ""
    except Exception:
        logger.warning("Tavily extract failed for %s", url, exc_info=True)
    return ""


def _search_tavily_for_trends() -> list[dict[str, Any]]:
    api_key = (config.TRAVILY_API_KEY or "").strip()
    if not api_key:
        return []
    try:
        from tavily import TavilyClient

        from scrapper.tavily_retry import tavily_search_with_retry

        client = TavilyClient(api_key=api_key)
        pages: list[dict[str, Any]] = []
        for query in TAVILY_TREND_QUERIES[:3]:
            response = tavily_search_with_retry(
                client,
                query=query,
                search_depth="advanced",
                max_results=5,
                include_answer=True,
            )
            if not response:
                continue
            if response.get("answer"):
                pages.append(
                    {
                        "source": "Tavily Search",
                        "url": query,
                        "content": response.get("answer") or "",
                    }
                )
            for item in response.get("results") or []:
                content = item.get("content") or item.get("raw_content") or ""
                if not content:
                    continue
                pages.append(
                    {
                        "source": item.get("title") or "Tavily",
                        "url": item.get("url") or "",
                        "content": content,
                    }
                )
        return pages
    except Exception:
        logger.exception("Tavily trend search failed")
        return []


async def _fetch_source(source: dict[str, str]) -> dict[str, Any] | None:
    url = source["url"]
    name = source["name"]
    focus = source.get("focus") or ""
    content = ""
    try:
        content = await _fetch_with_httpx(url)
    except Exception:
        logger.warning("HTTP fetch failed for %s, trying Tavily extract", url)
        content = await asyncio.to_thread(_fetch_with_tavily_extract, url)

    if not content or len(content) < 200:
        return None

    parsed = parse_source_content(content, source=name, focus=focus)
    parsed["url"] = url
    parsed["content_length"] = len(content)
    return parsed


async def crawl_instagram_web_trends(*, region: str | None = None) -> dict[str, Any]:
    """Crawl trend websites, Google Trends RSS, and Tavily search results."""
    source_tasks = [_fetch_source(source) for source in TREND_SOURCES]
    google_task = fetch_google_trends(region=region)

    html_pages, google_result = await asyncio.gather(
        asyncio.gather(*source_tasks),
        google_task,
    )
    parsed_pages = [page for page in html_pages if page]

    if google_result.get("parsed_page"):
        parsed_pages.append(google_result["parsed_page"])

    tavily_pages = await asyncio.to_thread(_search_tavily_for_trends)
    for page in tavily_pages:
        parsed_pages.append(
            parse_source_content(
                page.get("content") or "",
                source=page.get("source") or "Tavily",
                focus="hashtags,topics,songs,reel_formats,culture",
            )
        )

    if not parsed_pages:
        return {
            "success": False,
            "error": "Could not fetch trend data from web sources. Check network or TRAVILY_API_KEY.",
            "sources": [],
            "parsed_pages": [],
        }

    sources = [page.get("source") for page in parsed_pages]
    if google_result.get("sources"):
        sources.extend(google_result["sources"])

    return {
        "success": True,
        "sources": sources,
        "parsed_pages": parsed_pages,
        "google_trends": google_result.get("trends") or [],
        "google_trend_geos": google_result.get("geo_codes") or [],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
