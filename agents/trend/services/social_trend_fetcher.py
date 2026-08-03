import asyncio
import logging
import re
from typing import Any

import httpx

from agents.trend.services.web_trend_parser import parse_reddit_posts, parse_source_content
from agents.trend.services.web_trend_sources import TAVILY_TREND_QUERIES

logger = logging.getLogger(__name__)

REDDIT_SUBREDDIT_RE = re.compile(r"reddit\.com/r/([^/?#]+)", re.IGNORECASE)
SOCIAL_TAVILY_QUERIES = [
    query
    for query in TAVILY_TREND_QUERIES
    if any(
        token in query.lower()
        for token in ("reddit", " x ", "x trending", "facebook", "linkedin")
    )
]


def reddit_source_label(url: str, base_name: str = "Reddit") -> str:
    match = REDDIT_SUBREDDIT_RE.search(url or "")
    if match:
        return f"{base_name} (r/{match.group(1)})"
    return base_name


def classify_source(source: dict[str, str]) -> str:
    url = (source.get("url") or "").lower()
    name = (source.get("name") or "").lower()
    if "reddit.com/r/linkedin" in url:
        return "linkedin_reddit"
    if "reddit.com" in url or name == "reddit":
        return "reddit"
    if "linkedin.com" in url or name == "linkedin":
        return "linkedin"
    if "x.com" in url or "twitter.com" in url or name == "x":
        return "x"
    if "facebook.com" in url or name.startswith("facebook"):
        return "facebook"
    return "html"


def linkedin_source_label(url: str, base_name: str = "LinkedIn") -> str:
    match = REDDIT_SUBREDDIT_RE.search(url or "")
    if match:
        return f"{base_name} (r/{match.group(1)})"
    if "pulse/topic/" in (url or ""):
        topic = url.rstrip("/").split("/")[-1]
        return f"{base_name} ({topic})"
    return base_name


async def fetch_reddit_subreddit(
    source: dict[str, str],
    *,
    limit: int = 25,
) -> dict[str, Any] | None:
    url = source["url"].rstrip("/")
    json_url = f"{url}/hot.json?limit={limit}&raw_json=1"
    label = reddit_source_label(url, source.get("name") or "Reddit")
    headers = {
        "User-Agent": "TrendBot/1.0 (web trend aggregator)",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            response = await client.get(json_url, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except Exception:
        logger.debug("Reddit JSON fetch failed for %s", url, exc_info=True)
        return None

    posts = (payload.get("data") or {}).get("children") or []
    if not posts:
        return None

    parsed = parse_reddit_posts(posts, source=label, focus=source.get("focus") or "")
    parsed["source"] = label
    parsed["url"] = url
    parsed["platform"] = "reddit"
    parsed["post_count"] = len(posts)
    return parsed


async def fetch_social_via_tavily_extract(
    source: dict[str, str],
    session: Any,
) -> dict[str, Any] | None:
    from agents.trend.services.web_trend_crawler import _fetch_with_tavily_extract

    url = source["url"]
    name = source.get("name") or "Social"
    focus = source.get("focus") or ""
    content = await asyncio.to_thread(_fetch_with_tavily_extract, url, session)
    if not content or len(content) < 150:
        return None

    parsed = parse_source_content(content, source=name, focus=focus)
    parsed["source"] = name
    parsed["url"] = url
    parsed["platform"] = classify_source(source)
    parsed["content_length"] = len(content)
    return parsed


def search_social_trends_via_tavily(session: Any) -> list[dict[str, Any]]:
    if session.disabled:
        return []

    from agents.trend.services.web_trend_crawler import _TavilySession
    from config.credential_config import config
    from scrapper.tavily_retry import is_tavily_unreachable_error, tavily_search_with_retry
    from tavily import TavilyClient

    if not isinstance(session, _TavilySession):
        return []

    api_key = (config.TRAVILY_API_KEY or "").strip()
    if not api_key:
        return []

    pages: list[dict[str, Any]] = []
    try:
        client = TavilyClient(api_key=api_key)
        for query in SOCIAL_TAVILY_QUERIES[:10]:
            if session.disabled:
                break
            response = tavily_search_with_retry(
                client,
                query=query,
                search_depth="advanced",
                max_results=5,
                include_answer=True,
            )
            if not response:
                continue

            platform = (
                "Reddit"
                if "reddit" in query.lower()
                else "LinkedIn"
                if "linkedin" in query.lower()
                else "X"
                if " x " in query.lower() or query.lower().startswith("x ")
                else "Facebook"
            )
            if response.get("answer"):
                pages.append(
                    {
                        "source": f"{platform} (Tavily)",
                        "url": query,
                        "content": response.get("answer") or "",
                        "platform": platform.lower(),
                        "focus": "hashtags,topics,reel_formats,culture",
                    }
                )
            for item in response.get("results") or []:
                content = item.get("content") or item.get("raw_content") or ""
                if not content:
                    continue
                pages.append(
                    {
                        "source": f"{platform} ({item.get('title') or 'Tavily'})",
                        "url": item.get("url") or query,
                        "content": content,
                        "platform": platform.lower(),
                        "focus": "hashtags,topics,reel_formats,culture",
                    }
                )
    except Exception as exc:
        if is_tavily_unreachable_error(exc):
            session.mark_unreachable(exc)
        else:
            logger.warning("Social Tavily search failed: %s", exc)
    return pages
