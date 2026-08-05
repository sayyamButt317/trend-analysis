from typing import Any
from core.exceptions import AuthenticationError, RateLimitError
from service.AnalyzeUserLinkedIn.B2Bpositioning import build_linkedin_analysis
from service.AnalyzeUserLinkedIn.companypage import run_playwright_session
from service.AnalyzeUserLinkedIn.hiring import (
    build_hiring_signals,
    fetch_employees_tavily,
    fetch_jobs_tavily,
    merge_employees,
)
from service.AnalyzeUserLinkedIn.posts import fetch_linkedin_posts_tavily
from service.AnalyzeUserLinkedIn.safety import USER_EMPLOYEE_LIMIT
from service.AnalyzeUserLinkedIn.urls import build_company_urls_from_name


async def fetch_linkedin_company_intel(
    company_name: str,
    *,
    linkedin_url: str | None = None,
    post_limit: int = 10,
    employee_limit: int = USER_EMPLOYEE_LIMIT,
    job_limit: int = 10,
    skip_playwright: bool = False,
    runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch LinkedIn posts, employees, and job openings for a company page."""
    company_name = (company_name or "").strip()
    if not company_name:
        return {"posts": [], "employees": [], "jobs": [], "company_size": None}

    urls = build_company_urls_from_name(company_name, linkedin_url=linkedin_url)
    posts: list[dict[str, Any]] = []
    employees: list[dict[str, Any]] = []
    jobs: list[dict[str, Any]] = []
    company_size: str | None = None
    playwright_error: str | None = None

    if not skip_playwright:
        try:
            session = await run_playwright_session(
                company_name,
                linkedin_url=linkedin_url,
                post_limit=post_limit,
                employee_limit=employee_limit,
                job_limit=job_limit,
                runtime=runtime,
            )
            posts = session.get("posts") or []
            employees = session.get("employees") or []
            jobs = session.get("jobs") or []
            company_size = session.get("company_size")
        except RateLimitError as exc:
            playwright_error = str(exc)
        except AuthenticationError as exc:
            playwright_error = str(exc)

    # Fill toward the requested employee_limit (Playwright rarely returns everyone).
    if len(employees) < employee_limit:
        tavily_employees = await fetch_employees_tavily(company_name, limit=employee_limit)
        employees = merge_employees(employees, tavily_employees, limit=employee_limit)
    if not jobs:
        jobs = await fetch_jobs_tavily(company_name, limit=job_limit)
    if not posts:
        posts = await fetch_linkedin_posts_tavily(
            company_name,
            linkedin_url=linkedin_url,
            limit=post_limit,
        )

    hiring_signals = build_hiring_signals(jobs)
    capped_employees = employees[:employee_limit]
    return {
        "posts": posts[:post_limit],
        "employees": capped_employees,
        "jobs": jobs[:job_limit],
        "job_openings": jobs[:job_limit],
        "company_size": company_size,
        "employee_count": len(capped_employees),
        "job_count": len(jobs),
        "hiring_signals": hiring_signals,
        "is_hiring": bool(jobs),
        "linkedin_url": linkedin_url or urls["company_url"],
        "linkedin_posts_url": urls["posts_url"],
        "linkedin_slug": urls["slug"],
        "playwright_error": playwright_error,
    }


async def analyze_user_linkedin(
    company: dict[str, Any],
    *,
    company_name: str,
    linkedin_url: str | None = None,
    post_limit: int = 10,
    employee_limit: int = USER_EMPLOYEE_LIMIT,
    job_limit: int = 10,
    skip_playwright: bool = False,
    runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch and analyze the requesting company's LinkedIn presence."""
    company_name = (company_name or company.get("name") or "").strip()
    if not company_name:
        return {
            "skipped": True,
            "reason": "No company name provided",
            "warnings": ["Provide company name in company_data to analyze LinkedIn."],
        }

    urls = build_company_urls_from_name(company_name, linkedin_url=linkedin_url)
    linkedin_url = linkedin_url or urls["company_url"]
    posts_url = urls["posts_url"]

    intel = await fetch_linkedin_company_intel(
        company_name,
        linkedin_url=linkedin_url,
        post_limit=post_limit,
        employee_limit=employee_limit,
        job_limit=job_limit,
        skip_playwright=skip_playwright,
        runtime=runtime,
    )
    posts = intel.get("posts") or []
    employees = intel.get("employees") or []
    jobs = intel.get("jobs") or intel.get("job_openings") or []
    company_size = intel.get("company_size")

    analysis = (
        build_linkedin_analysis(
            posts,
            employees=employees,
            jobs=jobs,
            company_size=company_size,
        )
        if posts or employees
        else None
    )

    warnings: list[str] = []
    if intel.get("playwright_error"):
        warnings.append(intel["playwright_error"])
    if not posts:
        warnings.append(f"Could not fetch LinkedIn posts from {posts_url}.")
    if not employees:
        warnings.append("No employees found on LinkedIn (people page may require login).")
    if not jobs:
        warnings.append("No open job listings found on LinkedIn for this company.")

    return {
        "skipped": False,
        "company_name": company_name,
        "linkedin_url": linkedin_url,
        "linkedin_posts_url": posts_url,
        "linkedin_slug": urls["slug"],
        "linkedin_posts": posts,
        "linkedin_analysis": analysis,
        "linkedin_content_themes": (analysis or {}).get("content_themes") or [],
        "employees": employees,
        "employee_count": len(employees),
        "job_openings": jobs,
        "company_size": company_size,
        "is_hiring": bool(jobs),
        "hiring_signals": intel.get("hiring_signals") or [],
        "social_handles": {"linkedin_url": linkedin_url},
        "warnings": warnings,
        "playwright_error": intel.get("playwright_error"),
    }
