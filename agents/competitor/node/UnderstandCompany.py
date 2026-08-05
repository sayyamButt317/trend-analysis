import logging
from typing import Any
from agents.competitor.pipeline_log import log_event
from agents.competitor.state.competitor_state import CompetitorState
from agents.trend.services.company_profile_parser import merge_company_with_profile
from models.company import CompanyInput
from service.Competitor.company_understanding import CompanyUnderstandingService
from service.Competitor.website_crawler import WebsiteCrawlerService


logger = logging.getLogger(__name__)


def _company_input_from_config(config: dict[str, Any]) -> CompanyInput:
    company = config.get("company") or {}
    filters = config.get("filters") or config
    profile_text = (
        company.get("profile")
        or config.get("company_profile")
        or config.get("company_description")
        or company.get("description")
        or ""
    )
    merged = merge_company_with_profile({"profile": profile_text, **company})
    return CompanyInput(
        name=(merged.get("name") or config.get("company_name") or "Company").strip(),
        website=merged.get("website") or config.get("company_website"),
        industry=filters.get("industry") or merged.get("industry"),
        description=merged.get("description") or profile_text[:2000],
        country=filters.get("country") or config.get("country"),
        city=filters.get("city") or config.get("city"),
        region=filters.get("region") or config.get("region"),
        profile_text=profile_text,

    )

async def UnderstandCompanyNode(state: CompetitorState) -> CompetitorState:
    config = state.get("config") or {}
    company_input = _company_input_from_config(config)
    log_event(
        "1_user_profile",
        "Parsing company input",
        company=company_input.name,
        website=company_input.website or "none",
        region=company_input.region,
    )

    website_intel = None
    if company_input.website:
        log_event("1_user_profile", "Crawling company website", url=company_input.website)
        crawler = WebsiteCrawlerService()
        extracted = await crawler.crawl_company_website(
            url=company_input.website,
            company_name=company_input.name,
        )
        if extracted:
            website_intel = extracted.model_dump()
            log_event(
                "1_user_profile",
                "Website crawl complete",
                pages=len(website_intel.get("pages") or []),
                socials=list((website_intel.get("social_links") or {}).keys()) or "none",
            )
    log_event("1_user_profile", "Running company understanding (LLM)", company=company_input.name)
    service = CompanyUnderstandingService()
    profile = await service.analyze(company_input, website_intel=website_intel)
    company_dict = profile.model_dump()
    existing = config.get("company") or {}
    config["company"] = {
        **existing,
        **company_dict,
        "instagram_username": existing.get("instagram_username") or company_dict.get("instagram_username"),
        "instagram_url": existing.get("instagram_url") or company_dict.get("instagram_url"),
        "linkedin_url": existing.get("linkedin_url") or company_dict.get("linkedin_url"),
    }
    config["company_name"] = profile.name
    config["company_profile"] = company_input.profile_text
    config["company_signals"] = {
        "name": profile.name,
        "services": profile.services,
        "flagship_services": profile.services[:3],
        "technologies": profile.technologies,
        "keywords": profile.keywords,
        "target_industries": profile.target_audience,
        "instagram_username": config["company"].get("instagram_username"),
        "linkedin_url": config["company"].get("linkedin_url"),
    }

    state["config"] = config
    state["company_profile"] = {**company_dict, **config["company"]}

    def _list_field(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str) and value.strip():
            return [part.strip() for part in value.split(",") if part.strip()]
        return []

    state["company_analysis"] = {
        **company_dict,
        "company_dna": {
            "services": _list_field(profile.services),
            "technologies": _list_field(profile.technologies),
            "keywords": _list_field(profile.keywords),
            "target_audience": _list_field(profile.target_audience),
            "positioning": profile.positioning,
            "value_proposition": profile.value_proposition,
        },
    }
    if website_intel:
        from service.Competitor.platforms import filter_competitor_socials

        if website_intel.get("social_links"):
            website_intel = {
                **website_intel,
                "social_links": filter_competitor_socials(website_intel["social_links"]),
            }
        state["web_crawl"] = website_intel
    log_event(
        "1_user_profile",
        "Company profile ready",
        services=len(profile.services),
        keywords=len(profile.keywords),
        instagram=config["company"].get("instagram_username") or "none",
        linkedin="yes" if config["company"].get("linkedin_url") else "none",
    )
    return state


