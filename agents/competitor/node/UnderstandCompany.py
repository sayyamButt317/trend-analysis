import logging
from typing import Any

from agents.competitor.pipeline_log import log_event
from agents.competitor.state.competitor_state import CompetitorState
from agents.trend.services.company_profile_parser import merge_company_with_profile
from models.company import CompanyInput
from service.Competitor.website_crawler import WebsiteCrawlerService
from service.Competitor.platforms import filter_competitor_socials

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

    merged = merge_company_with_profile(
        {
            "profile": profile_text,
            **company,
        }
    )

    return CompanyInput(
        name=(merged.get("name") or config.get("company_name") or "Company").strip(),
        website=merged.get("website") or config.get("company_website"),
        industry=merged.get("industry") or filters.get("industry"),
        description=merged.get("description") or profile_text,
        country=filters.get("country") or config.get("country"),
        city=filters.get("city") or config.get("city"),
        region=filters.get("region") or config.get("region"),
        profile_text=profile_text,
    )


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]

    if isinstance(value, str):
        return [
            item.strip()
            for item in value.split(",")
            if item.strip()
        ]

    return []


async def UnderstandCompanyNode(
    state: CompetitorState,
) -> CompetitorState:

    config = state.get("config") or {}

    company_input = _company_input_from_config(config)

    log_event(
        "1_company",
        "Building company profile",
        company=company_input.name,
    )

    website_data = {}

    if company_input.website:
        try:
            crawler = WebsiteCrawlerService()

            result = await crawler.crawl_company_website(
                url=company_input.website,
                company_name=company_input.name,
            )

            if result:
                website_data = result.model_dump()

                if website_data.get("social_links"):
                    website_data["social_links"] = (
                        filter_competitor_socials(
                            website_data["social_links"]
                        )
                    )

        except Exception:
            logger.exception("Website crawl failed")

    existing = config.get("company") or {}

    company = {
        **existing,
        "name": company_input.name,
        "website": company_input.website,
        "industry": company_input.industry,
        "description": company_input.description,
        "country": company_input.country,
        "city": company_input.city,
        "region": company_input.region,
        "instagram_username": existing.get("instagram_username"),
        "instagram_url": existing.get("instagram_url"),
        "linkedin_url": existing.get("linkedin_url"),
    }

    config["company"] = company
    config["company_name"] = company_input.name
    config["company_profile"] = company_input.profile_text

    company_signals = {
        "company_name": company_input.name,
        "industry": company_input.industry,
        "description": company_input.description,
        "country": company_input.country,
        "city": company_input.city,
        "region": company_input.region,
        "website": company_input.website,
        "instagram_username": company.get("instagram_username"),
        "linkedin_url": company.get("linkedin_url"),
    }

    config["company_signals"] = company_signals

    state["config"] = config

    state["company_profile"] = company

    state["company_analysis"] = {
        "company": company,
        "website": website_data,
        "company_dna": {
            "services": _list(existing.get("services")),
            "keywords": _list(existing.get("keywords")),
            "technologies": _list(existing.get("technologies")),
            "target_audience": _list(existing.get("target_audience")),
            "positioning": existing.get("positioning"),
            "value_proposition": existing.get("value_proposition"),
        },
    }

    if website_data:
        state["web_crawl"] = website_data

    log_event(
        "1_company",
        "Company profile ready",
        website="yes" if company_input.website else "no",
        instagram="yes" if company.get("instagram_username") else "no",
        linkedin="yes" if company.get("linkedin_url") else "no",
    )

    return state