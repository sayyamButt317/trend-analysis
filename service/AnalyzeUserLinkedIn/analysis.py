from typing import Any
from core.exceptions import AuthenticationError, RateLimitError
from service.AnalyzeUserLinkedIn.B2Bpositioning import build_linkedin_analysis
from service.AnalyzeUserLinkedIn.companypage import run_playwright_session
from service.AnalyzeUserLinkedIn.hiring import (
    build_hiring_signals,
    extract_founders_from_text,
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
    skip_employees: bool = False,
    runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    company_name = (company_name or "").strip()
    if not company_name:
        return {"posts": [], "c_level": [], "employees": [], "jobs": [], "company_size": None}

    urls = build_company_urls_from_name(company_name, linkedin_url=linkedin_url)
    posts: list[dict[str, Any]] = []
    employees: list[dict[str, Any]] = []
    jobs: list[dict[str, Any]] = []
    company_size: str | None = None
    playwright_error: str | None = None
    effective_employee_limit = 0 if skip_employees else employee_limit

    if not skip_playwright:
        try:
            session = await run_playwright_session(
                company_name,
                linkedin_url=linkedin_url,
                post_limit=post_limit,
                employee_limit=effective_employee_limit,
                job_limit=job_limit,
                runtime=runtime,
            )
            posts = session.get("posts") or []
            employees = [] if skip_employees else (session.get("employees") or [])
            jobs = session.get("jobs") or []
            company_size = session.get("company_size")
        except RateLimitError as exc:
            playwright_error = str(exc)
        except AuthenticationError as exc:
            playwright_error = str(exc)

    if not skip_employees and effective_employee_limit > 0 and len(employees) < effective_employee_limit:
        tavily_employees = await fetch_employees_tavily(company_name, limit=effective_employee_limit)
        employees = merge_employees(employees, tavily_employees, limit=effective_employee_limit)
    if not jobs:
        jobs = await fetch_jobs_tavily(company_name, limit=job_limit)
    if not posts:
        posts = await fetch_linkedin_posts_tavily(
            company_name,
            linkedin_url=linkedin_url,
            limit=post_limit,
        )
    if not company_size:
        from service.Competitor.linkedin_employees import fetch_company_size_tavily

        company_size = await fetch_company_size_tavily(company_name, linkedin_url=linkedin_url)

    hiring_signals = build_hiring_signals(jobs)
    capped = [] if skip_employees else employees[: min(max(effective_employee_limit, 0), 3)]
    return {
        "posts": posts[:post_limit],
        "c_level": capped,
        "employees": capped,
        "jobs": jobs[:job_limit],
        "job_openings": jobs[:job_limit],
        "company_size": company_size,
        "employee_count": len(capped),
        "c_level_count": len(capped),
        "job_count": len(jobs),
        "hiring_signals": hiring_signals,
        "is_hiring": bool(jobs),
        "linkedin_url": linkedin_url or urls["company_url"],
        "linkedin_posts_url": urls["posts_url"],
        "linkedin_slug": urls["slug"],
        "playwright_error": playwright_error,
        "skip_employees": skip_employees,
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
    skip_employees: bool = False,
    runtime: dict[str, Any] | None = None,
    website_text: str | None = None,
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
        skip_employees=skip_employees,
        runtime=runtime,
    )
    posts = intel.get("posts") or []
    c_level = [] if skip_employees else (intel.get("c_level") or intel.get("employees") or [])
    jobs = intel.get("jobs") or intel.get("job_openings") or []
    company_size = intel.get("company_size")

    if not skip_employees and not c_level:
        fallback_blob = "\n".join(
            str(part)
            for part in (
                website_text,
                company.get("description"),
                company.get("profile"),
                company.get("company_summary_text"),
                company.get("about"),
            )
            if part
        )
        founders = extract_founders_from_text(
            fallback_blob,
            company_name=company_name,
            limit=min(employee_limit or 3, 3),
        )
        if founders:
            c_level = founders

    analysis = (
        build_linkedin_analysis(
            posts,
            employees=c_level,
            jobs=jobs,
            company_size=company_size,
        )
        if posts or c_level
        else None
    )

    warnings: list[str] = []
    if intel.get("playwright_error"):
        warnings.append(intel["playwright_error"])
    if not posts:
        warnings.append(f"Could not fetch LinkedIn posts from {posts_url}.")
    if not skip_employees:
        if not c_level:
            warnings.append(
                "No C-level LinkedIn profiles found (CEO/CTO/founder/etc.). "
                "People page may require login or titles were not visible."
            )
        elif any(person.get("source") == "website_text" for person in c_level):
            warnings.append(
                "C-level filled from website/about text because LinkedIn people scrape returned none."
            )
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
        "c_level": c_level,
        "c_level_count": len(c_level),
        "employees": c_level,  # backward-compatible alias
        "employee_count": len(c_level),
        "job_openings": jobs,
        "company_size": company_size,
        "is_hiring": bool(jobs),
        "hiring_signals": intel.get("hiring_signals") or [],
        "social_handles": {"linkedin_url": linkedin_url},
        "warnings": warnings,
        "playwright_error": intel.get("playwright_error"),
        "skip_employees": skip_employees,
    }
