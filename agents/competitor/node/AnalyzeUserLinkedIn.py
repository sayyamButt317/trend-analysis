import logging

from agents.competitor.pipeline_log import log_event
from agents.competitor.node.user_social_utils import (
    apply_user_linkedin_insights,
    enrich_company_profile_for_discovery,
    merge_company_analysis,
)
from agents.competitor.state.competitor_state import CompetitorState
from service.AnalyzeUserLinkedIn import analyze_user_linkedin, build_company_urls_from_name
from service.AnalyzeUserLinkedIn.safety import USER_EMPLOYEE_LIMIT, linkedin_safety_config

logger = logging.getLogger(__name__)


async def AnalyzeUserLinkedInNode(state: CompetitorState) -> CompetitorState:
    config = state.get("config") or {}
    filters = config.get("filters") or config
    company = dict(config.get("company") or {})
    post_limit = min(int(filters.get("post_limit") or config.get("post_limit") or 10), 10)
    company_name = (config.get("company_name") or company.get("name") or "").strip()
    linkedin_url = (config.get("company_linkedin_url") or company.get("linkedin_url") or "").strip() or None

    if not company_name:
        log_event("1_user_profile", "User LinkedIn skipped — no company name")
        merge_company_analysis(state, {"user_linkedin": {"skipped": True, "reason": "not_provided"}})
        enrich_company_profile_for_discovery(state)
        return state

    if config.get("skip_linkedin"):
        log_event("1_user_profile", "User LinkedIn skipped — serverless mode")
        merge_company_analysis(
            state,
            {"user_linkedin": {"skipped": True, "reason": "serverless_skip_linkedin"}},
        )
        enrich_company_profile_for_discovery(state)
        return state

    urls = build_company_urls_from_name(company_name, linkedin_url=linkedin_url)
    safety = linkedin_safety_config(config.get("runtime_profile"))
    employee_limit = int(
        filters.get("user_employee_limit")
        or config.get("user_employee_limit")
        or safety.get("user_employee_limit")
        or USER_EMPLOYEE_LIMIT
    )
    log_event(
        "1_user_profile",
        "Scraping user LinkedIn (Playwright + Tavily fallback)",
        company=company_name,
        posts_url=urls["posts_url"],
        post_limit=post_limit,
        employee_limit=employee_limit,
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
        logger.exception("User LinkedIn analysis failed for %s", company_name)
        merge_company_analysis(
            state,
            {
                "user_linkedin": {
                    "skipped": False,
                    "company_name": company_name,
                    "linkedin_posts_url": urls["posts_url"],
                    "warnings": ["LinkedIn analysis failed due to an internal error."],
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
            "LinkedIn blocked or challenged the Playwright session. "
            "Analysis continues using Tavily fallback. "
            "To restore full LinkedIn scraping: verify your account in a browser, "
            "set LINKEDIN_LI_AT in .env, or wait 1–24h before retrying."
        )
        result["warnings"] = warnings
        # Do not set state["error"] — competitor analysis should continue

    linkedin_url = result.get("linkedin_url") or urls["company_url"]
    config = apply_user_linkedin_insights(
        config,
        linkedin_url=linkedin_url,
        analysis=result.get("linkedin_analysis"),
        posts=result.get("linkedin_posts") or [],
    )
    if result.get("is_hiring"):
        hiring_keywords = list(result.get("hiring_signals") or [])[:5]
        existing = list((config.get("filters") or {}).get("keywords") or [])
        for kw in hiring_keywords:
            if kw and kw not in existing:
                existing.append(kw)
        config.setdefault("filters", {})["keywords"] = existing[:20]
        config["is_hiring"] = True

    config["company_linkedin_url"] = linkedin_url
    config["company"]["linkedin_url"] = linkedin_url
    state["config"] = config
    state["linkedin_posts"] = result.get("linkedin_posts") or []

    merge_company_analysis(
        state,
        {
            "user_linkedin": result,
            "linkedin_url": linkedin_url,
            "linkedin_posts_url": result.get("linkedin_posts_url") or urls["posts_url"],
            "linkedin_analysis": result.get("linkedin_analysis"),
            "linkedin_content_themes": result.get("linkedin_content_themes") or [],
            "employees": result.get("employees") or [],
            "job_openings": result.get("job_openings") or [],
            "company_size": result.get("company_size"),
            "is_hiring": result.get("is_hiring"),
            "social_handles": {
                **((state.get("company_analysis") or {}).get("social_handles") or {}),
                **(result.get("social_handles") or {}),
            },
        },
    )
    enrich_company_profile_for_discovery(state)

    log_event(
        "1_user_profile",
        "User LinkedIn analyzed",
        company=company_name,
        posts=len(result.get("linkedin_posts") or []),
        employees=len(result.get("employees") or []),
        jobs=len(result.get("job_openings") or []),
        hiring=result.get("is_hiring"),
    )
    return state
