import logging
from typing import Any

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

    website_intel = None
    if company_input.website:
        crawler = WebsiteCrawlerService()
        extracted = await crawler.crawl_company_website(
            url=company_input.website,
            company_name=company_input.name,
        )
        if extracted:
            website_intel = extracted.model_dump()

    service = CompanyUnderstandingService()
    profile = await service.analyze(company_input, website_intel=website_intel)

    company_dict = profile.model_dump()
    config["company"] = {**(config.get("company") or {}), **company_dict}
    config["company_name"] = profile.name
    config["company_profile"] = company_input.profile_text
    config["company_signals"] = {
        "name": profile.name,
        "services": profile.services,
        "flagship_services": profile.services[:3],
        "technologies": profile.technologies,
        "keywords": profile.keywords,
        "target_industries": profile.target_audience,
    }

    state["config"] = config
    state["company_profile"] = company_dict
    state["company_analysis"] = company_dict
    if website_intel:
        state["web_crawl"] = website_intel
    return state
