import asyncio
import logging
from typing import Any

from service.AnalyzeUserLinkedIn.hiring import scrape_employees_from_page, scrape_jobs_from_page
from service.AnalyzeUserLinkedIn.posts import scrape_posts_from_page
from service.AnalyzeUserLinkedIn.safety import clamp_playwright_limits, linkedin_safety_config
from service.AnalyzeUserLinkedIn.session import LinkedInPlaywrightSession, run_linkedin_playwright
from service.AnalyzeUserLinkedIn.urls import build_company_urls_from_name

logger = logging.getLogger(__name__)


async def fetch_company_size_from_page(session: LinkedInPlaywrightSession, base_url: str) -> str | None:
    if not await session.navigate(base_url, purpose="company_size"):
        return None
    try:
        size_text = await session.page.evaluate(
            """() => {
            for (const item of document.querySelectorAll('.org-top-card-summary-info-list__info-item, span, div')) {
                const text = (item.innerText || '').trim();
                if (/employee/i.test(text)) return text;
            }
            return null;
        }"""
        )
        return str(size_text) if size_text else None
    except Exception:
        logger.debug("LinkedIn company size scrape failed", exc_info=True)
        return None


async def run_playwright_session(
    company_name: str,
    *,
    linkedin_url: str | None = None,
    post_limit: int,
    employee_limit: int,
    job_limit: int,
    runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safety = linkedin_safety_config(runtime)
    post_limit, employee_limit, job_limit = clamp_playwright_limits(
        post_limit=post_limit,
        employee_limit=employee_limit,
        job_limit=job_limit,
        safety=safety,
    )

    async def _session() -> dict[str, Any]:
        async with LinkedInPlaywrightSession(runtime=runtime) as li_session:
            posts = await scrape_posts_from_page(
                li_session,
                company_name=company_name,
                linkedin_url=linkedin_url,
                limit=post_limit,
            )
            if li_session.is_blocked:
                return {"posts": posts, "employees": [], "jobs": [], "company_size": None}

            employees = await scrape_employees_from_page(
                li_session,
                company_name=company_name,
                linkedin_url=linkedin_url,
                limit=employee_limit,
            )
            jobs = await scrape_jobs_from_page(
                li_session,
                company_name=company_name,
                linkedin_url=linkedin_url,
                limit=job_limit,
            )
            base = build_company_urls_from_name(company_name, linkedin_url=linkedin_url)[
                "company_url"
            ].rstrip("/")
            company_size = await fetch_company_size_from_page(li_session, base)

        return {
            "posts": posts,
            "employees": employees,
            "jobs": jobs,
            "company_size": company_size,
        }

    try:
        return await run_linkedin_playwright(_session)
    except Exception as exc:
        from core.exceptions import AuthenticationError, RateLimitError

        if isinstance(exc, (RateLimitError, AuthenticationError)):
            raise
        logger.debug("LinkedIn Playwright intel session unavailable", exc_info=True)
    return {}
