import logging
from typing import Any

from agents.competitor.pipeline_log import log_event
from agents.competitor.state.competitor_state import CompetitorState
from agents.trend.services.company_social_analyzer import resolve_company_social_handles
from service.AnalyzeUserLinkedIn import (
    build_company_urls_from_name,
    build_linkedin_analysis,
    fetch_linkedin_company_intel,
    linkedin_safety_config,
)
from service.AnalyzeUserLinkedIn.safety import COMPETITOR_EMPLOYEE_LIMIT

logger = logging.getLogger(__name__)

Competitor = dict[str, Any]


async def analyze_competitor_linkedin(
    competitor: Competitor,
    *,
    region: str | None = None,
    post_limit: int = 10,
    employee_limit: int = COMPETITOR_EMPLOYEE_LIMIT,
    skip_playwright: bool = False,
    runtime: dict[str, Any] | None = None,
) -> Competitor:
    name = (competitor.get("name") or competitor.get("username") or "").strip()
    linkedin_url = competitor.get("linkedin_url") or (competitor.get("socials") or {}).get("linkedin")
    warnings: list[str] = list(competitor.get("social_warnings") or [])
    safety = linkedin_safety_config(runtime)
    employee_limit = int(
        (runtime or {}).get("competitor_employee_limit")
        or safety.get("competitor_employee_limit")
        or employee_limit
        or COMPETITOR_EMPLOYEE_LIMIT
    )

    if not linkedin_url and name:
        handles = await resolve_company_social_handles(
            {
                "name": name,
                "website": competitor.get("website"),
                "profile": competitor.get("bio") or "",
                "linkedin_url": competitor.get("linkedin_url"),
                "linkedin_username": competitor.get("linkedin_username"),
            },
            region=region,
            resolve_linkedin=True,
        )
        linkedin_url = handles.get("linkedin_url")
        if handles.get("linkedin_username"):
            competitor["linkedin_username"] = handles["linkedin_username"]

    enriched = dict(competitor)
    if not name:
        warnings.append("No competitor name found for LinkedIn analysis.")
        enriched["social_warnings"] = warnings
        enriched["linkedin_analysis"] = None
        enriched["employees"] = []
        return enriched

    if not linkedin_url:
        linkedin_url = build_company_urls_from_name(name)["company_url"]

    use_playwright = not skip_playwright and safety["scrape_competitors_with_playwright"]
    if not use_playwright:
        warnings.append(
            "Competitor LinkedIn uses Tavily only (safer for your account). "
            "Set LINKEDIN_SCRAPE_COMPETITORS=true to enable Playwright for competitors."
        )

    intel = await fetch_linkedin_company_intel(
        name,
        linkedin_url=linkedin_url,
        post_limit=post_limit,
        employee_limit=employee_limit,
        job_limit=5,
        skip_playwright=not use_playwright,
        runtime=runtime,
    )
    posts = intel.get("posts") or []
    employees = intel.get("employees") or []
    jobs = intel.get("jobs") or intel.get("job_openings") or []

    if not posts:
        urls = build_company_urls_from_name(name, linkedin_url=linkedin_url)
        warnings.append(f"Could not fetch LinkedIn posts from {urls['posts_url']}.")
    if not employees:
        warnings.append(f"No LinkedIn employees found for {name} (target {employee_limit}).")

    analysis = build_linkedin_analysis(
        posts,
        employees=employees,
        jobs=jobs,
        company_size=intel.get("company_size"),
    )
    enriched.update(
        {
            "linkedin_url": linkedin_url,
            "linkedin_posts": posts,
            "linkedin_analysis": analysis,
            "employees": employees[:employee_limit],
            "employee_count": len(employees[:employee_limit]),
            "job_openings": jobs,
            "company_size": intel.get("company_size"),
            "is_hiring": bool(jobs),
            "hiring_signals": intel.get("hiring_signals") or [],
            "social_warnings": warnings,
        }
    )
    return enriched


async def analyzeCompetitorLinkedin(competitor: Competitor) -> Competitor:
    return await analyze_competitor_linkedin(competitor)


async def AnalyzeCompetitorLinkedinNode(state: CompetitorState) -> CompetitorState:
    if state.get("error"):
        return state

    config = state.get("config") or {}
    if config.get("skip_linkedin"):
        log_event("3_competitor_social", "Competitor LinkedIn skipped — serverless mode")
        return state

    filters = config.get("filters") or config
    region = filters.get("region") or config.get("region")
    post_limit = min(int(filters.get("post_limit") or config.get("post_limit") or 15), 10)
    runtime = config.get("runtime_profile") or {}
    safety = linkedin_safety_config(runtime)
    employee_limit = int(
        filters.get("competitor_employee_limit")
        or config.get("competitor_employee_limit")
        or safety.get("competitor_employee_limit")
        or COMPETITOR_EMPLOYEE_LIMIT
    )
    skip_playwright = bool(config.get("skip_playwright")) or not safety["scrape_competitors_with_playwright"]

    competitors = state.get("discovered_influencers") or state.get("competitors") or []
    enriched: list[Competitor] = []
    playwright_budget = safety["max_playwright_competitors"]
    log_event(
        "3_competitor_social",
        "Analyzing competitor LinkedIn pages",
        competitors=len(competitors),
        playwright="enabled" if not skip_playwright else "tavily_only",
        post_limit=post_limit,
        employee_limit=employee_limit,
    )

    for index, competitor in enumerate(competitors):
        competitor_skip_playwright = skip_playwright
        if not skip_playwright and index >= playwright_budget:
            competitor_skip_playwright = True

        name = competitor.get("name") or competitor.get("username")
        log_event(
            "3_competitor_social",
            "Competitor LinkedIn",
            name=name,
            mode="playwright" if not competitor_skip_playwright else "tavily",
            employee_limit=employee_limit,
        )

        try:
            item = await analyze_competitor_linkedin(
                competitor,
                region=region,
                post_limit=post_limit,
                employee_limit=employee_limit,
                skip_playwright=competitor_skip_playwright,
                runtime=runtime,
            )
            enriched.append(item)
            log_event(
                "3_competitor_social",
                "Competitor employees fetched",
                name=name,
                employees=len(item.get("employees") or []),
            )
        except Exception:
            logger.exception(
                "LinkedIn analysis failed for competitor=%s",
                competitor.get("username") or competitor.get("name"),
            )
            enriched.append({**competitor, "linkedin_analysis": None, "employees": []})

    state["discovered_influencers"] = enriched
    state["competitors"] = enriched
    analyzed = sum(1 for item in enriched if item.get("linkedin_analysis"))
    total_employees = sum(len(item.get("employees") or []) for item in enriched)
    log_event(
        "3_competitor_social",
        "Competitor LinkedIn analysis finished",
        analyzed=analyzed,
        total=len(enriched),
        employees_total=total_employees,
    )
    return state
