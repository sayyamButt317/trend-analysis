import asyncio
import logging
import re
from datetime import datetime, timezone
from html import unescape
from typing import Any
from tavily import TavilyClient
from scrapper.tavily_retry import (
    is_tavily_unreachable_error,
    tavily_extract_counted,
    tavily_search_with_retry,
)
import httpx
from agents.trend.services.google_trend_fetcher import fetch_google_trends
from agents.trend.services.social_trend_fetcher import (
    classify_source,
    fetch_linkedin_source,
    fetch_reddit_subreddit,
    fetch_social_platform_boost,
    fetch_social_via_tavily_extract,
    fetch_x_source,
    linkedin_source_label,
    search_social_trends_via_tavily,
)
from agents.trend.services.web_trend_parser import (
    build_source_breakdown,
    extract_platform_trends,
    parse_source_content,
)
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


class _TavilySession:
    def __init__(self) -> None:
        self.disabled = False
        self.disable_reason: str | None = None

    def mark_unreachable(self, exc: Exception) -> None:
        if self.disabled:
            return
        self.disabled = True
        self.disable_reason = str(exc)
        logger.warning(
            "Tavily unreachable (DNS/network). Continuing with Google Trends and direct HTTP only."
        )


def _fetch_with_tavily_extract(url: str, session: _TavilySession) -> str:
    if session.disabled:
        return ""

    api_key = (config.TRAVILY_API_KEY or "").strip()
    if not api_key:
        session.disabled = True
        session.disable_reason = "TRAVILY_API_KEY not configured"
        return ""

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        if hasattr(client, "extract"):
            result = tavily_extract_counted(client, urls=[url])
            chunks = result.get("results") or []
            if chunks:
                return chunks[0].get("raw_content") or chunks[0].get("content") or ""
    except Exception as exc:
        if is_tavily_unreachable_error(exc):
            session.mark_unreachable(exc)
        else:
            logger.warning("Tavily extract failed for %s: %s", url, exc)
    return ""


def _search_tavily_for_trends(session: _TavilySession) -> list[dict[str, Any]]:
    if session.disabled:
        return []
    api_key = (config.TRAVILY_API_KEY or "").strip()
    if not api_key:
        return []
    try:
        client = TavilyClient(api_key=api_key)
        pages: list[dict[str, Any]] = []
        for query in TAVILY_TREND_QUERIES[:6]:
            if session.disabled:
                break
            if any(token in query.lower() for token in ("reddit", "facebook", "linkedin")) or query.lower().startswith("x "):
                continue
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
    except Exception as exc:
        if is_tavily_unreachable_error(exc):
            session.mark_unreachable(exc)
        else:
            logger.warning("Tavily trend search failed: %s", exc)
        return []


async def _fetch_source(source: dict[str, str], session: _TavilySession) -> dict[str, Any] | None:
    source_type = classify_source(source)
    if source_type == "reddit":
        return await fetch_reddit_subreddit(source, session)
    if source_type == "linkedin_reddit":
        parsed = await fetch_reddit_subreddit(source, session)
        if parsed:
            parsed["source"] = linkedin_source_label(source["url"])
            parsed["platform"] = "linkedin"
        return parsed
    if source_type in {"x", "facebook"}:
        if source_type == "x":
            return await fetch_x_source(source, session)
        parsed = await fetch_social_via_tavily_extract(source, session)
        if parsed:
            return parsed
        return None
    if source_type == "linkedin":
        return await fetch_linkedin_source(source, session)

    url = source["url"]
    name = source["name"]
    focus = source.get("focus") or ""
    content = ""
    try:
        content = await _fetch_with_httpx(url)
    except Exception:
        if not session.disabled:
            logger.debug("HTTP fetch failed for %s, trying Tavily extract", url)
            content = await asyncio.to_thread(_fetch_with_tavily_extract, url, session)

    if not content or len(content) < 200:
        if source_type == "facebook" and not session.disabled:
            return await fetch_social_via_tavily_extract(source, session)
        return None

    parsed = parse_source_content(content, source=name, focus=focus)
    parsed["url"] = url
    parsed["platform"] = source_type if source_type != "html" else "web"
    parsed["content_length"] = len(content)
    return parsed


async def crawl_instagram_web_trends(*, region: str | None = None) -> dict[str, Any]:
    tavily_session = _TavilySession()
    source_tasks = [_fetch_source(source, tavily_session) for source in TREND_SOURCES]
    google_task = fetch_google_trends(region=region)

    html_pages, google_result, boost_pages = await asyncio.gather(
        asyncio.gather(*source_tasks),
        google_task,
        fetch_social_platform_boost(tavily_session),
    )
    parsed_pages = [page for page in html_pages if page]
    parsed_pages.extend(boost_pages)

    if google_result.get("parsed_page"):
        parsed_pages.append(google_result["parsed_page"])

    tavily_pages: list[dict[str, Any]] = []
    if not tavily_session.disabled:
        tavily_pages = await asyncio.to_thread(_search_tavily_for_trends, tavily_session)
        social_pages = await asyncio.to_thread(search_social_trends_via_tavily, tavily_session)
        tavily_pages.extend(social_pages)

    for page in tavily_pages:
        parsed = parse_source_content(
            page.get("content") or "",
            source=page.get("source") or "Tavily",
            focus=page.get("focus") or "hashtags,topics,reel_formats,culture",
        )
        parsed["url"] = page.get("url")
        parsed["platform"] = page.get("platform") or "tavily"
        parsed_pages.append(parsed)

    if not parsed_pages:
        return {
            "success": False,
            "error": (
                "Could not fetch trend data from any source. "
                "Check internet connectivity (Google Trends RSS and blog URLs)."
            ),
            "sources": [],
            "parsed_pages": [],
            "tavily_skipped": tavily_session.disabled,
            "tavily_skip_reason": tavily_session.disable_reason,
        }

    sources = [page.get("source") for page in parsed_pages if page.get("source")]
    if google_result.get("sources"):
        for source in google_result["sources"]:
            if source not in sources:
                sources.append(source)

    source_breakdown = build_source_breakdown(parsed_pages)
    platform_summary = _summarize_by_platform(source_breakdown)
    reddit_trends = extract_platform_trends(parsed_pages, "reddit")
    linkedin_trends = extract_platform_trends(parsed_pages, "linkedin")
    x_trends = extract_platform_trends(parsed_pages, "x")

    warnings: list[str] = []
    if tavily_session.disabled:
        warnings.append(
            "Tavily was skipped (DNS/network unavailable). "
            "Results use Google Trends RSS and direct website fetches."
        )

    return {
        "success": True,
        "sources": sources,
        "parsed_pages": parsed_pages,
        "source_breakdown": source_breakdown,
        "platform_summary": platform_summary,
        "reddit_trends": reddit_trends,
        "linkedin_trends": linkedin_trends,
        "x_trends": x_trends,
        "google_trends": google_result.get("trends") or [],
        "google_trends_by_country": google_result.get("google_trends_by_country") or {},
        "top_queries_by_country": google_result.get("top_queries_by_country") or {},
        "rising_queries_by_country": google_result.get("rising_queries_by_country") or {},
        "google_trend_geos": google_result.get("geo_codes") or [],
        "tavily_skipped": tavily_session.disabled,
        "tavily_skip_reason": tavily_session.disable_reason,
        "warnings": warnings,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _summarize_by_platform(breakdown: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for entry in breakdown:
        platform = entry.get("platform") or "web"
        bucket = summary.setdefault(
            platform,
            {"source_count": 0, "total_items": 0, "sources": [], "highlights": []},
        )
        bucket["source_count"] += 1
        bucket["total_items"] += int((entry.get("counts") or {}).get("total") or 0)
        bucket["sources"].append(entry.get("source"))
        for topic in entry.get("topics") or []:
            label = topic.get("topic")
            if label and label not in bucket["highlights"]:
                bucket["highlights"].append(label)
        for tag in entry.get("hashtags") or []:
            label = tag.get("tag")
            if label and label not in bucket["highlights"]:
                bucket["highlights"].append(f"#{label}")
        for fmt in entry.get("reel_formats") or []:
            label = fmt.get("name")
            if label and label not in bucket["highlights"]:
                bucket["highlights"].append(label)
        bucket["highlights"] = bucket["highlights"][:6]
    return summary
