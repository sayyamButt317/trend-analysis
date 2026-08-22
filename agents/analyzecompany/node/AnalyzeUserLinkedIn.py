import logging
from copy import deepcopy
from agents.analyzecompany.pipeline_log import log_event
from agents.analyzecompany.node.user_social_utils import (
    apply_user_linkedin_insights,
    enrich_company_profile_for_discovery,
    merge_company_analysis,
)
from agents.analyzecompany.state.companystate import AnalyzeCompanyState
from service.AnalyzeUserLinkedIn import (
    analyze_user_linkedin,
    build_company_urls_from_name,
)

logger = logging.getLogger(__name__)


async def AnalyzeUserLinkedInNode(state: AnalyzeCompanyState) -> AnalyzeCompanyState:
    """LinkedIn GTM (+ DNA fallback only when website DNA is incomplete)."""
    config = state.get("config") or {}
    filters = config.get("filters") or config
    company = dict(config.get("company") or {})
    coverage = config.get("platform_coverage") or {}
    gtm_only = bool(
        config.get("linkedin_gtm_only")
        or config.get("skip_linkedin_dna")
        or coverage.get("website_dna_complete")
        or coverage.get("skip_linkedin_dna")
    )

    post_limit = min(
        int(filters.get("post_limit") or config.get("post_limit") or 10),
        10,
    )
    # When website already covered DNA, keep LinkedIn light (themes/hiring only).
    if gtm_only:
        post_limit = min(post_limit, 5)

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
        log_event("1_company", "User LinkedIn skipped — no company name")
        merge_company_analysis(
            state,
            {"user_linkedin": {"skipped": True, "reason": "not_provided"}},
        )
        enrich_company_profile_for_discovery(state)
        return state

    if config.get("skip_linkedin") or config.get("force_skip_linkedin"):
        log_event("1_company", "User LinkedIn skipped — covered by prior platform / flag")
        merge_company_analysis(
            state,
            {"user_linkedin": {"skipped": True, "reason": "skipped_by_routing"}},
        )
        enrich_company_profile_for_discovery(state)
        return state

    urls = build_company_urls_from_name(company_name, linkedin_url=linkedin_url)

    log_event(
        "1_company",
        "Scraping user LinkedIn"
        + (" (GTM only — website DNA already covered)" if gtm_only else " (DNA fallback + GTM)"),
        company=company_name,
        posts_url=urls["posts_url"],
        post_limit=post_limit,
    )

    try:
        result = await analyze_user_linkedin(
            company,
            company_name=company_name,
            linkedin_url=linkedin_url,
            post_limit=post_limit,
            employee_limit=0,
            skip_employees=True,
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
            "1_company",
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

    pipeline_warnings = list(state.get("warnings") or [])
    for warning in result.get("warnings") or []:
        if warning and warning not in pipeline_warnings:
            pipeline_warnings.append(warning)
    state["warnings"] = pipeline_warnings

    analysis = result.get("linkedin_analysis") or {}
    posts = result.get("linkedin_posts") or []
    jobs = result.get("job_openings") or []
    themes = result.get("linkedin_content_themes") or []
    company_size = result.get("company_size")
    is_hiring = result.get("is_hiring")
    linkedin_url = result.get("linkedin_url") or urls["company_url"]

    config = apply_user_linkedin_insights(
        config,
        linkedin_url=linkedin_url,
        analysis=analysis,
        posts=posts,
    )

    if is_hiring:
        hiring_keywords = list(result.get("hiring_signals") or [])
        existing_keywords = list((config.get("filters") or {}).get("keywords") or [])
        for keyword in hiring_keywords:
            if keyword and keyword not in existing_keywords:
                existing_keywords.append(keyword)
        config.setdefault("filters", {})["keywords"] = existing_keywords[:20]
        config["is_hiring"] = True

    company_signals = deepcopy(config.get("company_signals") or {})
    company_signals.update(
        {
            "linkedin_url": linkedin_url,
            "company_size": company_size,
            "is_hiring": is_hiring,
            "job_openings": jobs,
            "posting_frequency": analysis.get("posting_frequency"),
            "content_focus": analysis.get("content_focus"),
            "content_categories": analysis.get("content_categories"),
            "primary_content_category": analysis.get("primary_content_category"),
            "linkedin_themes": themes,
        }
    )
    company_signals.pop("c_level", None)
    company_signals.pop("c_level_count", None)
    config["company_signals"] = company_signals
    config["company_linkedin_url"] = linkedin_url
    config.setdefault("company", {})
    config["company"]["linkedin_url"] = linkedin_url
    state["config"] = config

    clean_result = {
        key: value
        for key, value in result.items()
        if key not in {"c_level", "c_level_count", "employees", "employee_count"}
    }

    state["linkedin_posts"] = posts
    state["user_linkedin"] = clean_result
    state["user_linkedin_analysis"] = analysis
    state["user_linkedin_profile"] = {
        "linkedin_url": linkedin_url,
        "company_size": company_size,
        "job_openings": jobs,
        "is_hiring": is_hiring,
    }
    state["linkedin_company_signals"] = {
        "company_size": company_size,
        "job_openings": jobs,
        "is_hiring": is_hiring,
        "content_themes": themes,
        "analysis": analysis,
    }

    merge_company_analysis(
        state,
        {
            "user_linkedin": clean_result,
            "linkedin_url": linkedin_url,
            "linkedin_posts_url": result.get("linkedin_posts_url") or urls["posts_url"],
            "linkedin_analysis": analysis,
            "linkedin_content_themes": themes,
            "job_openings": jobs,
            "company_size": company_size,
            "is_hiring": is_hiring,
            "social_handles": {
                **((state.get("company_analysis") or {}).get("social_handles") or {}),
                **(result.get("social_handles") or {}),
            },
        },
    )

    analysis_block = state.get("company_analysis") or {}
    for key in ("c_level", "c_level_count", "employees", "employee_count"):
        analysis_block.pop(key, None)
    state["company_analysis"] = analysis_block

    discovery = state.get("discovery_features") or {}
    discovery.update(
        {
            "linkedin_topics": themes,
            "linkedin_categories": analysis.get("content_categories") or [],
            "linkedin_primary_category": analysis.get("primary_content_category"),
            "linkedin_posting_frequency": analysis.get("posting_frequency"),
            "linkedin_content_focus": analysis.get("content_focus"),
            "is_hiring": is_hiring,
            "company_size": company_size,
        }
    )
    for key in ("c_level_count", "c_level_titles", "c_level_names"):
        discovery.pop(key, None)
    state["discovery_features"] = discovery
    enrich_company_profile_for_discovery(state)

    log_event(
        "1_company",
        "LinkedIn intelligence extracted",
        company=company_name,
        company_size=company_size or "unknown",
        jobs=len(jobs),
        themes=len(themes),
        hiring=is_hiring,
    )
    log_event(
        "1_company",
        "User LinkedIn analyzed",
        company=company_name,
        posts=len(posts),
        jobs=len(jobs),
        hiring=is_hiring,
        gtm_only=gtm_only,
    )
    from agents.analyzecompany.routing import mark_platform_coverage

    return mark_platform_coverage(state, source="linkedin")
