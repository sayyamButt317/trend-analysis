import logging
from copy import deepcopy

from agents.competitor.pipeline_log import log_event
from agents.competitor.node.user_social_utils import (
    apply_user_linkedin_insights,
    enrich_company_profile_for_discovery,
    merge_company_analysis,
)
from agents.competitor.state.competitor_state import CompetitorState
from service.AnalyzeUserLinkedIn import (
    analyze_user_linkedin,
    build_company_urls_from_name,
)
from service.AnalyzeUserLinkedIn.safety import (
    USER_EMPLOYEE_LIMIT,
    linkedin_safety_config,
)

logger = logging.getLogger(__name__)
async def AnalyzeUserLinkedInNode(state: CompetitorState) -> CompetitorState:
    config = state.get("config") or {}
    filters = config.get("filters") or config
    company = dict(config.get("company") or {})

    post_limit = min(
        int(filters.get("post_limit") or config.get("post_limit") or 10),
        10,
    )

    company_name = (
        config.get("company_name")
        or company.get("name")
        or ""
    ).strip()

    linkedin_url = (
        config.get("company_linkedin_url")
        or company.get("linkedin_url")
        or ""
    ).strip() or None

    if not company_name:
        log_event(
            "1_user_profile",
            "User LinkedIn skipped — no company name",
        )

        merge_company_analysis(
            state,
            {
                "user_linkedin": {
                    "skipped": True,
                    "reason": "not_provided",
                }
            },
        )

        enrich_company_profile_for_discovery(state)
        return state

    if config.get("skip_linkedin"):
        log_event(
            "1_user_profile",
            "User LinkedIn skipped — serverless mode",
        )

        merge_company_analysis(
            state,
            {
                "user_linkedin": {
                    "skipped": True,
                    "reason": "serverless_skip_linkedin",
                }
            },
        )

        enrich_company_profile_for_discovery(state)
        return state

    urls = build_company_urls_from_name(
        company_name,
        linkedin_url=linkedin_url,
    )

    safety = linkedin_safety_config(config.get("runtime_profile"))
    employee_limit = int(
        filters.get("user_employee_limit")
        or config.get("user_employee_limit")
        or safety.get("user_employee_limit")
        or USER_EMPLOYEE_LIMIT
    )

    log_event(
        "1_user_profile",
        "Scraping user LinkedIn",
        company=company_name,
        posts_url=urls["posts_url"],
        employee_limit=employee_limit,
        post_limit=post_limit,
    )

    try:
        result = await analyze_user_linkedin(
            company,
            company_name=company_name,
            linkedin_url=linkedin_url,
            post_limit=post_limit,
            employee_limit=employee_limit,
            skip_playwright=bool(config.get("skip_playwright")),
            runtime=config.get("runtime_profile"),
        )

    except Exception:
        logger.exception(
            "User LinkedIn analysis failed for %s",
            company_name,
        )

        merge_company_analysis(
            state,
            {
                "user_linkedin": {
                    "skipped": False,
                    "company_name": company_name,
                    "linkedin_posts_url": urls["posts_url"],
                    "warnings": [
                        "LinkedIn analysis failed due to an internal error."
                    ],
                }
            },
        )

        enrich_company_profile_for_discovery(state)
        return state

    if result.get("playwright_error"):
        log_event(
            "1_user_profile",
            "LinkedIn Playwright blocked — using Tavily fallback",
            company=company_name,
            reason=str(result["playwright_error"])[:80],
        )
        warnings = list(result.get("warnings") or [])
        warnings.append(
            "LinkedIn blocked the browser session. "
            "Analysis continued using Tavily fallback."
        )
        result["warnings"] = warnings

    analysis = result.get("linkedin_analysis") or {}
    posts = result.get("linkedin_posts") or []
    employees = result.get("employees") or []
    jobs = result.get("job_openings") or []
    themes = result.get("linkedin_content_themes") or []
    company_size = result.get("company_size")
    is_hiring = result.get("is_hiring")
    linkedin_url = result.get("linkedin_url") or urls["company_url"]
        # ---------------------------------------------------------
    # Apply LinkedIn insights to config
    # ---------------------------------------------------------

    config = apply_user_linkedin_insights(
        config,
        linkedin_url=linkedin_url,
        analysis=analysis,
        posts=posts,
    )

    # ---------------------------------------------------------
    # Hiring signals
    # ---------------------------------------------------------

    if is_hiring:
        hiring_keywords = list(result.get("hiring_signals") or [])

        existing_keywords = list(
            (config.get("filters") or {}).get("keywords") or []
        )

        for keyword in hiring_keywords:
            if keyword and keyword not in existing_keywords:
                existing_keywords.append(keyword)

        config.setdefault("filters", {})["keywords"] = existing_keywords[:20]

        config["is_hiring"] = True

    # ---------------------------------------------------------
    # Company Signals (used later by competitor discovery)
    # ---------------------------------------------------------

    company_signals = deepcopy(config.get("company_signals") or {})

    company_signals.update(
        {
            "linkedin_url": linkedin_url,
            "company_size": company_size,
            "employee_count": len(employees),
            "is_hiring": is_hiring,
            "job_openings": jobs,
            "posting_frequency": analysis.get("posting_frequency"),
            "content_focus": analysis.get("content_focus"),
            "content_categories": analysis.get("content_categories"),
            "primary_content_category": analysis.get(
                "primary_content_category"
            ),
            "linkedin_themes": themes,
            "employees": employees,
        }
    )

    config["company_signals"] = company_signals

    # ---------------------------------------------------------
    # Save into config
    # ---------------------------------------------------------

    config["company_linkedin_url"] = linkedin_url

    config.setdefault("company", {})
    config["company"]["linkedin_url"] = linkedin_url

    state["config"] = config

    # ---------------------------------------------------------
    # Store LinkedIn intelligence
    # ---------------------------------------------------------

    state["linkedin_posts"] = posts

    state["user_linkedin"] = result

    state["user_linkedin_analysis"] = analysis

    state["user_linkedin_profile"] = {
        "linkedin_url": linkedin_url,
        "company_size": company_size,
        "employees": employees,
        "employee_count": len(employees),
        "job_openings": jobs,
        "is_hiring": is_hiring,
    }

    state["linkedin_company_signals"] = {
        "company_size": company_size,
        "employee_count": len(employees),
        "job_openings": jobs,
        "is_hiring": is_hiring,
        "content_themes": themes,
        "analysis": analysis,
    }
        # ---------------------------------------------------------
    # Merge into company analysis
    # ---------------------------------------------------------

    merge_company_analysis(
        state,
        {
            "user_linkedin": result,
            "linkedin_url": linkedin_url,
            "linkedin_posts_url": result.get("linkedin_posts_url")
            or urls["posts_url"],
            "linkedin_analysis": analysis,
            "linkedin_content_themes": themes,
            "employees": employees,
            "job_openings": jobs,
            "company_size": company_size,
            "is_hiring": is_hiring,
            "social_handles": {
                **(
                    (state.get("company_analysis") or {})
                    .get("social_handles")
                    or {}
                ),
                **(result.get("social_handles") or {}),
            },
        },
    )

    # ---------------------------------------------------------
    # Discovery features used by competitor search
    # ---------------------------------------------------------

    discovery = state.get("discovery_features") or {}

    discovery.update(
        {
            "linkedin_topics": themes,
            "linkedin_categories": analysis.get("content_categories") or [],
            "linkedin_primary_category": analysis.get(
                "primary_content_category"
            ),
            "linkedin_posting_frequency": analysis.get(
                "posting_frequency"
            ),
            "linkedin_content_focus": analysis.get(
                "content_focus"
            ),
            "is_hiring": is_hiring,
            "company_size": company_size,
            "employee_count": len(employees),
            "job_titles": [
                employee.get("title")
                for employee in employees
                if employee.get("title")
            ],
            "skills": [
                skill
                for employee in employees
                for skill in (employee.get("skills") or [])
            ],
        }
    )

    state["discovery_features"] = discovery

    # ---------------------------------------------------------
    # Enrich company profile
    # ---------------------------------------------------------

    enrich_company_profile_for_discovery(state)

    # ---------------------------------------------------------
    # Pipeline log
    # ---------------------------------------------------------

    log_event(
        "1_user_profile",
        "LinkedIn intelligence extracted",
        company=company_name,
        company_size=company_size or "unknown",
        employees=len(employees),
        jobs=len(jobs),
        themes=len(themes),
        hiring=is_hiring,
    )

    log_event(
        "1_user_profile",
        "User LinkedIn analyzed",
        company=company_name,
        posts=len(posts),
        employees=len(employees),
        jobs=len(jobs),
        hiring=is_hiring,
    )

    return state