"""Conditional platform routing: skip next platform when prior already covered its fields."""

from __future__ import annotations

from typing import Any

from agents.analyzecompany.pipeline_log import log_event
from agents.analyzecompany.state.companystate import AnalyzeCompanyState


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return [item for item in value if item]
    return []


def _company(state: AnalyzeCompanyState) -> dict[str, Any]:
    config = state.get("config") or {}
    return dict(state.get("company_profile") or config.get("company") or {})


def website_dna_complete(state: AnalyzeCompanyState) -> bool:
    """Website already supplied core DNA — LinkedIn should not re-fetch those fields."""
    company = _company(state)
    website = dict(state.get("web_crawl") or (state.get("company_analysis") or {}).get("website") or {})
    services = _list(website.get("services")) or _list(company.get("services"))
    technologies = _list(website.get("technologies")) or _list(company.get("technologies"))
    industry = company.get("industry") or (_list(website.get("industries")) or [None])[0]
    business_model = website.get("business_model") or company.get("business_model")
    description = website.get("description") or website.get("summary") or company.get("description")
    # Strong enough to skip LinkedIn DNA fallback.
    return bool(services) and bool(technologies or business_model or industry) and bool(description or industry)


def has_instagram_handle(state: AnalyzeCompanyState) -> bool:
    config = state.get("config") or {}
    company = _company(state)
    username = (
        config.get("company_instagram_username")
        or company.get("instagram_username")
        or ""
    ).strip().lstrip("@")
    return bool(username)


def has_linkedin_target(state: AnalyzeCompanyState) -> bool:
    config = state.get("config") or {}
    company = _company(state)
    name = (config.get("company_name") or company.get("name") or "").strip()
    url = (config.get("company_linkedin_url") or company.get("linkedin_url") or "").strip()
    return bool(name or url)


def has_instagram_gtm(state: AnalyzeCompanyState) -> bool:
    config = state.get("config") or {}
    if config.get("user_instagram_analyzed"):
        return True
    ig = (state.get("company_analysis") or {}).get("user_instagram") or state.get("user_instagram") or {}
    analysis = ig.get("instagram") or state.get("user_instagram_analysis") or {}
    return bool(analysis.get("content_themes") or analysis.get("content_categories") or ig.get("profile"))


def has_linkedin_gtm(state: AnalyzeCompanyState) -> bool:
    config = state.get("config") or {}
    if config.get("user_linkedin_analyzed"):
        return True
    li = (state.get("company_analysis") or {}).get("user_linkedin") or state.get("user_linkedin") or {}
    return bool(li.get("linkedin_posts") or li.get("linkedin_analysis") or li.get("linkedin_content_themes"))


def needs_instagram(state: AnalyzeCompanyState) -> bool:
    config = state.get("config") or {}
    if config.get("skip_instagram") or config.get("force_skip_instagram"):
        return False
    if config.get("user_instagram_analyzed") or has_instagram_gtm(state):
        return False
    return has_instagram_handle(state)


def needs_linkedin(state: AnalyzeCompanyState) -> bool:
    """Run LinkedIn only for missing DNA and/or missing social GTM."""
    config = state.get("config") or {}
    if config.get("skip_linkedin") or config.get("force_skip_linkedin"):
        return False
    if config.get("user_linkedin_analyzed") or has_linkedin_gtm(state):
        return False
    if not has_linkedin_target(state):
        return False

    dna_ok = website_dna_complete(state)
    ig_ok = has_instagram_gtm(state) or not has_instagram_handle(state)

    # Website already has DNA + Instagram already covered social → skip LinkedIn entirely.
    if dna_ok and has_instagram_gtm(state):
        return False

    # Website DNA complete and no IG handle → still run LinkedIn for GTM/pain signals.
    if dna_ok and ig_ok and not has_instagram_handle(state):
        return True

    # DNA incomplete → LinkedIn as fallback DNA + GTM.
    if not dna_ok:
        return True

    # DNA complete, Instagram pending/skipped without themes → LinkedIn for GTM only.
    return not has_instagram_gtm(state)


def mark_platform_coverage(state: AnalyzeCompanyState, *, source: str) -> AnalyzeCompanyState:
    """Record what the last platform filled so later nodes can skip overlaps."""
    config = dict(state.get("config") or {})
    company = _company(state)
    coverage = dict(config.get("platform_coverage") or {})
    covered = set(coverage.get("fields") or [])

    if source == "website":
        for key, value in (
            ("services", company.get("services")),
            ("technologies", company.get("technologies")),
            ("keywords", company.get("keywords")),
            ("target_audience", company.get("target_audience")),
            ("industry", company.get("industry")),
            ("business_model", company.get("business_model")),
            ("positioning", company.get("positioning")),
            ("pricing", company.get("pricing")),
            ("description", company.get("description")),
        ):
            if value:
                covered.add(key)
        coverage["website_dna_complete"] = website_dna_complete(state)
    elif source == "instagram":
        covered.add("instagram_gtm")
        coverage["instagram_done"] = True
    elif source == "linkedin":
        covered.add("linkedin_gtm")
        coverage["linkedin_done"] = True
        # LinkedIn must not overwrite website DNA fields already covered.
        coverage["skip_linkedin_dna"] = bool(coverage.get("website_dna_complete"))

    coverage["fields"] = sorted(covered)
    coverage["skip_instagram"] = not needs_instagram(state)
    coverage["skip_linkedin"] = not needs_linkedin(state)
    config["platform_coverage"] = coverage
    # Tell LinkedIn node to skip DNA-style work when website already filled it.
    if coverage.get("website_dna_complete"):
        config["skip_linkedin_dna"] = True
        config["linkedin_gtm_only"] = True
    state["config"] = config
    return state


def route_after_website(state: AnalyzeCompanyState) -> str:
    if needs_instagram(state):
        log_event("1_company", "Route → Instagram (handle present, GTM still needed)")
        return "analyze_user_instagram"
    if needs_linkedin(state):
        reason = "DNA incomplete" if not website_dna_complete(state) else "GTM/pain still needed"
        log_event("1_company", f"Route → LinkedIn ({reason}); Instagram skipped")
        return "analyze_user_linkedin"
    log_event("1_company", "Route → Summary (website covered DNA; no social targets)")
    return "generate_company_summary"


def route_after_instagram(state: AnalyzeCompanyState) -> str:
    if needs_linkedin(state):
        reason = "DNA incomplete" if not website_dna_complete(state) else "LinkedIn GTM still needed"
        log_event("1_company", f"Route → LinkedIn ({reason})")
        return "analyze_user_linkedin"
    log_event(
        "1_company",
        "Route → Summary (skip LinkedIn — website DNA + Instagram GTM already covered)",
    )
    return "generate_company_summary"


def route_after_linkedin(state: AnalyzeCompanyState) -> str:
    return "generate_company_summary"
