import asyncio
import logging
from typing import Any

from config.credential_config import config
from scrapper.tavily_retry import is_tavily_unreachable_error, tavily_extract_counted, tavily_search_with_retry
from service.AnalyzeUserLinkedIn.session import LinkedInPlaywrightSession, run_linkedin_playwright
from service.AnalyzeUserLinkedIn.urls import (
    build_company_urls_from_name,
    linkedin_posts_path,
)
from service.AnalyzeUserLinkedIn.topics import extract_linkedin_themes

logger = logging.getLogger(__name__)


async def scrape_posts_from_page(
    session: LinkedInPlaywrightSession,
    *,
    company_name: str | None = None,
    linkedin_url: str | None = None,
    limit: int,
) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    posts_url = linkedin_posts_path(linkedin_url, company_name=company_name)
    if not await session.navigate(posts_url, purpose="company_posts"):
        return posts
    try:
        posts_data = await session.page.evaluate(
            """(limit) => {
            const results = [];
            const html = document.body.innerHTML;
            const urnMatches = [...html.matchAll(/urn:li:activity:(\\d+)/g)];
            const seen = new Set();
            for (const match of urnMatches) {
                const urn = match[0];
                if (seen.has(urn)) continue;
                seen.add(urn);
                const el = document.querySelector(`[data-urn="${urn}"]`);
                const text = el ? (el.innerText || '').trim() : '';
                if (text && text.length > 30) {
                    results.push({ urn, text: text.slice(0, 1500) });
                }
                if (results.length >= limit) break;
            }
            return results;
        }""",
            limit,
        )
        for item in posts_data or []:
            posts.append(
                {
                    "text": item.get("text"),
                    "urn": item.get("urn"),
                    "linkedin_url": posts_url,
                    "source": "linkedin_playwright",
                }
            )
    except Exception:
        logger.debug("LinkedIn posts scrape failed", exc_info=True)
    return posts


async def fetch_linkedin_posts_tavily(
    company_name: str,
    *,
    linkedin_url: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    api_key = (config.TRAVILY_API_KEY or "").strip()
    if not api_key:
        return []

    from tavily import TavilyClient

    posts: list[dict[str, Any]] = []
    posts_path = linkedin_posts_path(linkedin_url, company_name=company_name)
    company_url = build_company_urls_from_name(company_name)["company_url"]
    try:
        client = TavilyClient(api_key=api_key)
        if hasattr(client, "extract"):
            extract_result = tavily_extract_counted(
                client,
                count_as_linkedin=True,
                urls=[posts_path],
            )
            for chunk in extract_result.get("results") or []:
                content = chunk.get("raw_content") or chunk.get("content") or ""
                if content and len(content) > 100:
                    posts.append(
                        {
                            "text": content[:2000],
                            "source": "linkedin_extract",
                            "linkedin_url": company_url,
                        }
                    )

        response = tavily_search_with_retry(
            client,
            query=f'site:linkedin.com/posts OR site:linkedin.com/feed "{company_name}"',
            search_depth="advanced",
            max_results=limit,
            count_as_linkedin=True,
        )
        for item in (response or {}).get("results") or []:
            content = item.get("content") or item.get("raw_content") or ""
            if not content or len(content) < 60:
                continue
            posts.append(
                {
                    "text": content[:1500],
                    "title": item.get("title"),
                    "linkedin_url": item.get("url") or company_url,
                    "source": "linkedin_tavily",
                }
            )
    except Exception as exc:
        if not is_tavily_unreachable_error(exc):
            logger.warning("LinkedIn Tavily fetch failed: %s", exc)
    return posts[:limit]


async def _fetch_linkedin_posts_playwright_impl(
    company_name: str,
    *,
    linkedin_url: str | None = None,
    limit: int = 10,
    runtime: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    from service.AnalyzeUserLinkedIn.safety import clamp_playwright_limits, linkedin_safety_config

    safety = linkedin_safety_config(runtime)
    limit, _, _ = clamp_playwright_limits(post_limit=limit, employee_limit=0, job_limit=0, safety=safety)

    async def _run() -> list[dict[str, Any]]:
        async with LinkedInPlaywrightSession(runtime=runtime) as session:
            return await scrape_posts_from_page(
                session,
                company_name=company_name,
                linkedin_url=linkedin_url,
                limit=limit,
            )

    posts = await run_linkedin_playwright(_run)
    return posts[:limit]


async def fetch_linkedin_posts_playwright(
    company_name: str,
    *,
    linkedin_url: str | None = None,
    limit: int = 10,
    runtime: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    try:
        from core.browser import playwright_subprocess_supported, run_async_playwright_in_thread

        if playwright_subprocess_supported():
            return await _fetch_linkedin_posts_playwright_impl(
                company_name,
                linkedin_url=linkedin_url,
                limit=limit,
                runtime=runtime,
            )
        logger.info("Running LinkedIn Playwright fetch in background thread (Windows event loop fix)")
        return await run_async_playwright_in_thread(
            lambda: _fetch_linkedin_posts_playwright_impl(
                company_name,
                linkedin_url=linkedin_url,
                limit=limit,
                runtime=runtime,
            )
        )
    except Exception:
        logger.debug("LinkedIn Playwright fetch unavailable", exc_info=True)
    return []


async def fetch_linkedin_company_posts(
    company_name: str,
    *,
    linkedin_url: str | None = None,
    limit: int = 10,
    skip_playwright: bool = False,
    runtime: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not (company_name or "").strip():
        return []

    posts: list[dict[str, Any]] = []
    if not skip_playwright:
        posts = await fetch_linkedin_posts_playwright(
            company_name,
            linkedin_url=linkedin_url,
            limit=limit,
            runtime=runtime,
        )
    if not posts:
        posts = await fetch_linkedin_posts_tavily(
            company_name,
            linkedin_url=linkedin_url,
            limit=limit,
        )
    return posts


def summarize_linkedin_posts(posts: list[dict[str, Any]]) -> dict[str, Any]:
    texts = [post.get("text") or post.get("title") or "" for post in posts if post.get("text") or post.get("title")]
    avg_len = round(sum(len(text) for text in texts) / len(texts)) if texts else 0
    return {
        "post_count": len(posts),
        "avg_post_length": avg_len,
        "content_themes": extract_linkedin_themes(posts),
        "sample_posts": [
            {
                "text": (post.get("text") or post.get("title") or "")[:500],
                "source": post.get("source"),
                "linkedin_url": post.get("linkedin_url"),
            }
            for post in posts[:5]
        ],
    }
