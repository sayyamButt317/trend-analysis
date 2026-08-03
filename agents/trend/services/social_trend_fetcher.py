import asyncio
import logging
import re
from typing import Any
import httpx
from agents.trend.services.web_trend_parser import (
    parse_reddit_comments,
    parse_reddit_posts,
    parse_source_content,
)
from agents.trend.services.web_trend_sources import TAVILY_TREND_QUERIES

logger = logging.getLogger(__name__)

_PULLPUSH_LOCK = asyncio.Lock()

REDDIT_SUBREDDIT_RE = re.compile(r"reddit\.com/r/([^/?#]+)", re.IGNORECASE)
PULLPUSH_SUBMISSION_URL = "https://api.pullpush.io/reddit/search/submission/"
PULLPUSH_COMMENT_URL = "https://api.pullpush.io/reddit/search/comment/"
PULLPUSH_REQUEST_DELAY = 1.0

REDDIT_PULLPUSH_KEYWORDS = [
    "instagram",
    "reels",
    "marketing",
    "creator",
    "algorithm",
    "viral",
    "influencer",
    "social media",
]

REDDIT_PULLPUSH_EXTRA_SUBREDDITS = [
    "ContentCreation",
    "digital_marketing",
    "socialmediamarketing",
    "smallbusiness",
]

REDDIT_SITE_QUERIES = [
    "site:reddit.com/r/Instagram instagram reels algorithm trends",
    "site:reddit.com/r/socialmedia trending social media",
    "site:reddit.com/r/marketing viral marketing trends",
    "site:reddit.com/r/InstagramMarketing growth strategy",
]

X_SITE_QUERIES = [
    "site:x.com instagram marketing trends",
    "site:x.com social media viral trends 2026",
    "site:x.com creator economy trends",
    "site:twitter.com trending marketing hashtags",
    "site:x.com reels algorithm update",
    "site:x.com influencer marketing trends",
]

LINKEDIN_SITE_QUERIES = [
    "site:linkedin.com/pulse instagram marketing trends",
    "site:linkedin.com/posts social media trends 2026",
    "site:linkedin.com/pulse creator economy trends",
    "site:linkedin.com/business/marketing blog trends",
    "site:linkedin.com/pulse instagram reels strategy",
    "site:linkedin.com/posts viral marketing 2026",
]

SOCIAL_TAVILY_QUERIES = [
    *REDDIT_SITE_QUERIES,
    *LINKEDIN_SITE_QUERIES,
    *X_SITE_QUERIES,
    *[
        query
        for query in TAVILY_TREND_QUERIES
        if any(
            token in query.lower()
            for token in ("reddit", " x ", "x trending", "facebook", "linkedin")
        )
    ],
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


def x_source_label(url: str, base_name: str = "X") -> str:
    lowered = (url or "").lower()
    if "explore" in lowered and "trending" in lowered:
        return f"{base_name} (Trending)"
    if "/status/" in lowered:
        handle = lowered.split("x.com/")[-1].split("/")[0] if "x.com/" in lowered else ""
        if handle:
            return f"{base_name} (@{handle})"
    return base_name


async def fetch_reddit_subreddit(
    source: dict[str, str],
    *,
    limit: int = 25,
) -> dict[str, Any] | None:
    url = source["url"].rstrip("/")
    label = reddit_source_label(url, source.get("name") or "Reddit")
    match = REDDIT_SUBREDDIT_RE.search(url)
    if not match:
        return None
    subreddit = match.group(1)

    posts = await _fetch_reddit_pullpush(subreddit, limit=limit)
    if not posts:
        posts = await _fetch_reddit_json_fallback(url, limit=limit)
    if not posts:
        logger.info("Reddit fetch empty for r/%s", subreddit)
        return None

    parsed = parse_reddit_posts(posts, source=label, focus=source.get("focus") or "")
    parsed["source"] = label
    parsed["url"] = url
    parsed["platform"] = "reddit"
    parsed["post_count"] = len(posts)
    return parsed


async def _pullpush_get(url: str, params: dict[str, Any], *, retries: int = 4) -> list[dict[str, Any]]:
    headers = {"User-Agent": "TrendBot/1.0 (web trend aggregator)"}
    async with _PULLPUSH_LOCK:
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                    response = await client.get(url, params=params, headers=headers)
                    if response.status_code == 429:
                        wait = PULLPUSH_REQUEST_DELAY * (2**attempt) + 1.0
                        logger.debug("PullPush rate limited, retry in %.1fs", wait)
                        await asyncio.sleep(wait)
                        continue
                    response.raise_for_status()
                    data = response.json().get("data") or []
                    await asyncio.sleep(PULLPUSH_REQUEST_DELAY)
                    return data
            except Exception:
                if attempt >= retries - 1:
                    logger.debug("PullPush request failed %s %s", url, params, exc_info=True)
                    return []
                await asyncio.sleep(PULLPUSH_REQUEST_DELAY * (attempt + 1))
        return []


def _normalize_pullpush_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items:
        title = (item.get("title") or "").strip()
        body = (item.get("selftext") or item.get("body") or "").strip()
        if not title and not body:
            continue
        normalized.append(
            {
                "title": title,
                "selftext": body,
                "body": body,
                "ups": item.get("score") or item.get("ups") or 0,
                "link_flair_text": item.get("link_flair_text") or item.get("flair") or "",
                "permalink": item.get("permalink"),
                "subreddit": item.get("subreddit") or "",
            }
        )
    return normalized


def _reddit_page_from_items(
    items: list[dict[str, Any]],
    *,
    source: str,
    url: str,
    focus: str = "topics,hashtags,culture",
    kind: str = "submission",
) -> dict[str, Any] | None:
    if not items:
        return None
    if kind == "comment":
        parsed = parse_reddit_comments(items, source=source, focus=focus)
    else:
        parsed = parse_reddit_posts(_normalize_pullpush_items(items), source=source, focus=focus)
    if not (parsed.get("topics") or parsed.get("hashtags") or parsed.get("reel_formats")):
        return None
    parsed["source"] = source
    parsed["url"] = url
    parsed["platform"] = "reddit"
    parsed["post_count"] = len(items)
    return parsed


async def fetch_reddit_pullpush_boost() -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []

    for subreddit in REDDIT_PULLPUSH_EXTRA_SUBREDDITS:
        items = await _pullpush_get(
            PULLPUSH_SUBMISSION_URL,
            {
                "subreddit": subreddit,
                "size": 30,
                "sort": "desc",
                "sort_type": "score",
            },
        )
        await asyncio.sleep(PULLPUSH_REQUEST_DELAY)
        label = f"Reddit (r/{subreddit})"
        page = _reddit_page_from_items(
            items,
            source=label,
            url=f"https://www.reddit.com/r/{subreddit}/",
        )
        if page:
            pages.append(page)

    for keyword in REDDIT_PULLPUSH_KEYWORDS:
        items = await _pullpush_get(
            PULLPUSH_SUBMISSION_URL,
            {
                "q": keyword,
                "size": 25,
                "sort": "desc",
                "sort_type": "score",
            },
        )
        await asyncio.sleep(PULLPUSH_REQUEST_DELAY)
        page = _reddit_page_from_items(
            items,
            source=f"Reddit (search: {keyword})",
            url=f"{PULLPUSH_SUBMISSION_URL}?q={keyword}",
        )
        if page:
            pages.append(page)

    for keyword in REDDIT_PULLPUSH_KEYWORDS[:6]:
        items = await _pullpush_get(
            PULLPUSH_COMMENT_URL,
            {
                "q": keyword,
                "size": 20,
                "sort": "desc",
                "sort_type": "score",
            },
        )
        await asyncio.sleep(PULLPUSH_REQUEST_DELAY)
        page = _reddit_page_from_items(
            items,
            source=f"Reddit (comments: {keyword})",
            url=f"{PULLPUSH_COMMENT_URL}?q={keyword}",
            kind="comment",
        )
        if page:
            pages.append(page)

    logger.info("PullPush Reddit boost: %s pages", len(pages))
    return pages


async def _fetch_reddit_pullpush(subreddit: str, *, limit: int = 25) -> list[dict[str, Any]]:
    items = await _pullpush_get(
        PULLPUSH_SUBMISSION_URL,
        {
            "subreddit": subreddit,
            "size": limit,
            "sort": "desc",
            "sort_type": "score",
        },
    )
    return _normalize_pullpush_items(items)


async def _fetch_reddit_json_fallback(url: str, *, limit: int = 25) -> list[dict[str, Any]]:
    json_url = f"{url.rstrip('/')}/hot.json?limit={limit}&raw_json=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; TrendBot/1.0; +https://github.com/techtimize/trend)",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            response = await client.get(json_url, headers=headers)
            if response.status_code != 200:
                return []
            payload = response.json()
    except Exception:
        return []
    return (payload.get("data") or {}).get("children") or []


async def fetch_x_source(
    source: dict[str, str],
    session: Any,
) -> dict[str, Any] | None:
    url = source["url"]
    focus = source.get("focus") or "topics,hashtags,culture"
    label = x_source_label(url, source.get("name") or "X")
    content = ""

    if "help.x.com" in url or "help.twitter.com" in url:
        content = await _fetch_x_html(url)

    if not content or len(content) < 150:
        content = await asyncio.to_thread(_fetch_with_tavily_extract, url, session)

    if not content or len(content) < 150:
        content = await _fetch_x_via_tavily_search(session, url)

    if not content or len(content) < 100:
        return None

    parsed = parse_source_content(content, source=label, focus=focus)
    parsed["source"] = label
    parsed["url"] = url
    parsed["platform"] = "x"
    parsed["content_length"] = len(content)
    return parsed


async def _fetch_x_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            from agents.trend.services.web_trend_crawler import _html_to_text
            return _html_to_text(response.text)
    except Exception:
        logger.debug("X HTML fetch failed for %s", url, exc_info=True)
        return ""


async def _fetch_x_via_tavily_search(session: Any, context_url: str) -> str:
    from agents.trend.services.web_trend_crawler import _TavilySession
    from config.credential_config import config
    from scrapper.tavily_retry import tavily_search_with_retry
    from tavily import TavilyClient

    if not isinstance(session, _TavilySession) or session.disabled:
        return ""

    api_key = (config.TRAVILY_API_KEY or "").strip()
    if not api_key:
        return ""

    chunks: list[str] = []
    try:
        client = TavilyClient(api_key=api_key)
        for query in X_SITE_QUERIES:
            response = tavily_search_with_retry(
                client,
                query=query,
                search_depth="advanced",
                max_results=5,
            )
            for item in (response or {}).get("results") or []:
                item_url = (item.get("url") or "").lower()
                if not any(domain in item_url for domain in ("x.com", "twitter.com")):
                    continue
                content = item.get("content") or item.get("raw_content") or ""
                if content:
                    title = item.get("title") or ""
                    chunks.append(f"{title}\n{content}" if title else content)
            if response and response.get("answer"):
                chunks.append(response["answer"])
    except Exception:
        logger.debug("X Tavily search fallback failed for %s", context_url, exc_info=True)
    return "\n\n".join(chunks)[:8000]


async def fetch_linkedin_source(
    source: dict[str, str],
    session: Any,
) -> dict[str, Any] | None:
    url = source["url"]
    name = source.get("name") or "LinkedIn"
    focus = source.get("focus") or "topics,hashtags,culture"
    label = linkedin_source_label(url, name)
    content = ""

    if "linkedin.com/business" in url or "business.linkedin.com" in url:
        content = await _fetch_linkedin_html(url)

    if not content or len(content) < 150:
        content = await asyncio.to_thread(_fetch_with_tavily_extract, url, session)

    if not content or len(content) < 150:
        content = await _fetch_linkedin_via_tavily_search(session, url)

    if not content or len(content) < 100:
        return None

    parsed = parse_source_content(content, source=label, focus=focus)
    parsed["source"] = label
    parsed["url"] = url
    parsed["platform"] = "linkedin"
    parsed["content_length"] = len(content)
    return parsed


async def _fetch_linkedin_html(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
    }
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            from agents.trend.services.web_trend_crawler import _html_to_text
            return _html_to_text(response.text)
    except Exception:
        logger.debug("LinkedIn HTML fetch failed for %s", url, exc_info=True)
        return ""


async def _fetch_linkedin_via_tavily_search(session: Any, context_url: str) -> str:
    from agents.trend.services.web_trend_crawler import _TavilySession
    from config.credential_config import config
    from scrapper.tavily_retry import tavily_search_with_retry
    from tavily import TavilyClient

    if not isinstance(session, _TavilySession) or session.disabled:
        return ""

    api_key = (config.TRAVILY_API_KEY or "").strip()
    if not api_key:
        return ""

    chunks: list[str] = []
    try:
        client = TavilyClient(api_key=api_key)
        for query in LINKEDIN_SITE_QUERIES[:3]:
            response = tavily_search_with_retry(
                client,
                query=query,
                search_depth="advanced",
                max_results=5,
            )
            for item in (response or {}).get("results") or []:
                content = item.get("content") or item.get("raw_content") or ""
                if content:
                    chunks.append(content)
            if response and response.get("answer"):
                chunks.append(response["answer"])
    except Exception:
        logger.debug("LinkedIn Tavily search fallback failed for %s", context_url, exc_info=True)
    return "\n\n".join(chunks)[:8000]


def _fetch_with_tavily_extract(url: str, session: Any) -> str:
    from agents.trend.services.web_trend_crawler import _fetch_with_tavily_extract
    return _fetch_with_tavily_extract(url, session)


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
        for query in SOCIAL_TAVILY_QUERIES[:18]:
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
                if "site:reddit.com" in query.lower() or query in REDDIT_SITE_QUERIES
                else "LinkedIn"
                if "site:linkedin.com" in query.lower() or query in LINKEDIN_SITE_QUERIES
                else "X"
                if "site:x.com" in query.lower() or "site:twitter.com" in query.lower() or query in X_SITE_QUERIES
                else "Reddit"
                if "reddit" in query.lower()
                else "LinkedIn"
                if "linkedin" in query.lower()
                else "X"
                if " x " in query.lower() or query.lower().startswith("x ")
                else "Facebook"
            )
            if response.get("answer") and platform != "X":
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
                item_url = (item.get("url") or "").lower()
                if platform == "Reddit" and "reddit.com" not in item_url:
                    continue
                if platform == "LinkedIn" and "linkedin.com" not in item_url:
                    continue
                if platform == "X" and not any(domain in item_url for domain in ("x.com", "twitter.com")):
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


def fetch_platform_tavily_pages(
    platform: str,
    queries: list[str],
    session: Any,
    *,
    max_results: int = 8,
) -> list[dict[str, Any]]:
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

    platform_key = platform.lower()
    pages: list[dict[str, Any]] = []
    domain_checks = {
        "reddit": ("reddit.com",),
        "linkedin": ("linkedin.com",),
        "x": ("x.com", "twitter.com"),
    }
    allowed_domains = domain_checks.get(platform_key, ())

    try:
        client = TavilyClient(api_key=api_key)
        for query in queries:
            if session.disabled:
                break
            response = tavily_search_with_retry(
                client,
                query=query,
                search_depth="advanced",
                max_results=max_results,
                include_answer=False,
            )
            if not response:
                continue
            for item in response.get("results") or []:
                content = item.get("content") or item.get("raw_content") or ""
                if len(content) < 80:
                    continue
                item_url = (item.get("url") or "").lower()
                if allowed_domains and not any(domain in item_url for domain in allowed_domains):
                    continue
                title = item.get("title") or platform
                source_label = f"{platform} ({title})"
                parsed = parse_source_content(
                    content,
                    source=source_label,
                    focus="topics,hashtags,culture,reel_formats",
                )
                if not (parsed.get("topics") or parsed.get("hashtags") or parsed.get("reel_formats")):
                    continue
                parsed["source"] = source_label
                parsed["url"] = item.get("url") or query
                parsed["platform"] = platform_key
                parsed["content_length"] = len(content)
                pages.append(parsed)
    except Exception as exc:
        if is_tavily_unreachable_error(exc):
            session.mark_unreachable(exc)
        else:
            logger.warning("%s Tavily page fetch failed: %s", platform, exc)
    return pages


async def fetch_social_platform_boost(session: Any) -> list[dict[str, Any]]:
    reddit_task = fetch_reddit_pullpush_boost()
    linkedin_task = asyncio.to_thread(
        fetch_platform_tavily_pages,
        "LinkedIn",
        LINKEDIN_SITE_QUERIES,
        session,
        max_results=8,
    )
    x_task = asyncio.to_thread(
        fetch_platform_tavily_pages,
        "X",
        X_SITE_QUERIES,
        session,
        max_results=8,
    )
    reddit_pages, linkedin_pages, x_pages = await asyncio.gather(
        reddit_task,
        linkedin_task,
        x_task,
    )
    boost_pages = reddit_pages + linkedin_pages + x_pages
    logger.info(
        "Social platform boost: reddit=%s linkedin=%s x=%s",
        len(reddit_pages),
        len(linkedin_pages),
        len(x_pages),
    )
    return boost_pages
