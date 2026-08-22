import logging
import re
from typing import Any
from urllib.parse import urlparse
from agents.analyzecompany.pipeline_log import log_event
from agents.analyzecompany.state.companystate import AnalyzeCompanyState
from agents.trend.schemas.competitor_request import (
    normalize_instagram_username,
    normalize_linkedin_url,
)
from agents.trend.services.company_profile_parser import merge_company_with_profile
from models.company import CompanyInput
from service.Competitor.platforms import filter_competitor_socials
from service.Competitor.website_crawler import WebsiteCrawlerService
from agents.analyzecompany.routing import mark_platform_coverage
import logging

logger = logging.getLogger(__name__)


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _merge_unique(*groups: list[str], limit: int = 30) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            key = item.lower().strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item.strip())
            if len(out) >= limit:
                return out
    return out


def _name_from_website(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
    host = host.removeprefix("www.")
    if not host or "." not in host:
        return None
    slug = host.split(".")[0]
    if not slug or slug in {"www", "app", "site"}:
        return None
    return slug.replace("-", " ").replace("_", " ").title()


def _instagram_from_socials(social_links: dict[str, Any]) -> str | None:
    raw = (
        social_links.get("instagram")
        or social_links.get("instagram_url")
        or social_links.get("ig")
    )
    if not raw:
        return None
    text = str(raw).strip()
    if "instagram.com" in text.lower():
        match = re.search(r"instagram\.com/([A-Za-z0-9._]+)", text, re.I)
        handle = match.group(1) if match else ""
    else:
        handle = text.lstrip("@")
    return normalize_instagram_username(handle)


def _linkedin_from_socials(social_links: dict[str, Any]) -> str | None:
    raw = social_links.get("linkedin") or social_links.get("linkedin_url")
    if not raw:
        return None
    return normalize_linkedin_url(str(raw))


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
    website = (
        config.get("website_url")
        or config.get("company_website")
        or company.get("website")
        or ""
    ).strip() or None

    merged = merge_company_with_profile(
        {
            "profile": profile_text or (f"Company website: {website}" if website else ""),
            **company,
            "website": website or company.get("website"),
        }
    )

    name = (
        merged.get("name")
        or config.get("company_name")
        or _name_from_website(website)
        or "Company"
    ).strip()

    return CompanyInput(
        name=name,
        website=website or merged.get("website"),
        industry=merged.get("industry") or filters.get("industry"),
        description=merged.get("description") or profile_text,
        country=filters.get("country") or config.get("country"),
        city=filters.get("city") or config.get("city"),
        region=filters.get("region") or config.get("region"),
        profile_text=profile_text,
    )


async def UnderstandCompanyNode(state: AnalyzeCompanyState) -> AnalyzeCompanyState:
    config = state.get("config") or {}
    company_input = _company_input_from_config(config)

    log_event(
        "1_company",
        "Building company profile from website",
        company=company_input.name,
        website=company_input.website or "none",
    )

    website_data: dict[str, Any] = {}
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
                    website_data["social_links"] = filter_competitor_socials(
                        website_data["social_links"]
                    )
        except Exception:
            logger.exception("Website crawl failed for %s", company_input.website)
    else:
        log_event("1_company", "No website_url provided — skipping website crawl")

    existing = dict(config.get("company") or {})
    social_links = dict(website_data.get("social_links") or {})

    instagram_username = (
        existing.get("instagram_username")
        or config.get("company_instagram_username")
        or _instagram_from_socials(social_links)
    )
    linkedin_url = (
        existing.get("linkedin_url")
        or config.get("company_linkedin_url")
        or _linkedin_from_socials(social_links)
    )

    services = _merge_unique(
        _list(existing.get("services")),
        _list(website_data.get("services")),
        _list(website_data.get("products")),
        limit=30,
    )
    technologies = _merge_unique(
        _list(existing.get("technologies")),
        _list(website_data.get("technologies")),
        limit=30,
    )
    keywords = _merge_unique(
        _list(existing.get("keywords")),
        _list(website_data.get("keywords")),
        _list(website_data.get("features")),
        limit=40,
    )
    audience = _merge_unique(
        _list(existing.get("target_audience")),
        _list(website_data.get("target_audience")),
        limit=20,
    )

    description = (
        website_data.get("description")
        or company_input.description
        or existing.get("description")
        or company_input.profile_text
    )
    positioning = (
        website_data.get("positioning")
        or existing.get("positioning")
    )
    industry = (
        company_input.industry
        or (website_data.get("industries") or [None])[0]
        or existing.get("industry")
    )
    name = (
        website_data.get("company_name")
        or company_input.name
        or existing.get("name")
        or "Company"
    )

    company = {
        **existing,
        "name": name,
        "website": company_input.website or existing.get("website"),
        "industry": industry,
        "description": description,
        "country": company_input.country,
        "city": company_input.city,
        "region": company_input.region,
        "services": services,
        "technologies": technologies,
        "keywords": keywords,
        "target_audience": audience,
        "positioning": positioning,
        "value_proposition": existing.get("value_proposition") or website_data.get("value_proposition"),
        "business_model": website_data.get("business_model") or existing.get("business_model"),
        "pricing": website_data.get("pricing_model") or existing.get("pricing"),
        "instagram_username": instagram_username,
        "instagram_url": (
            f"https://www.instagram.com/{instagram_username}/" if instagram_username else existing.get("instagram_url")
        ),
        "linkedin_url": linkedin_url,
        "profile": company_input.profile_text or description,
    }

    config["company"] = company
    config["company_name"] = name
    config["company_profile"] = company_input.profile_text or description
    config["company_website"] = company.get("website")
    config["website_url"] = company.get("website")
    config["company_instagram_username"] = instagram_username
    config["company_linkedin_url"] = linkedin_url
    config["company_signals"] = {
        "company_name": name,
        "industry": industry,
        "description": description,
        "country": company_input.country,
        "city": company_input.city,
        "region": company_input.region,
        "website": company.get("website"),
        "services": services,
        "technologies": technologies,
        "keywords": keywords,
        "instagram_username": instagram_username,
        "linkedin_url": linkedin_url,
    }
    state["config"] = config
    state["company_profile"] = company
    state["company_analysis"] = {
        "company": company,
        "website": website_data,
        "company_dna": {
            "services": services,
            "keywords": keywords,
            "technologies": technologies,
            "target_audience": audience,
            "positioning": positioning,
            "value_proposition": company.get("value_proposition"),
            "business_model": company.get("business_model"),
            "pricing": company.get("pricing"),
            "industries": _list(website_data.get("industries")),
        },
    }
    if website_data:
        state["web_crawl"] = website_data

    log_event(
        "1_company",
        "Company profile ready",
        website="yes" if company_input.website else "no",
        crawled="yes" if website_data else "no",
        services=len(services),
        instagram="yes" if company.get("instagram_username") else "no",
        linkedin="yes" if company.get("linkedin_url") else "no",
    )

    return mark_platform_coverage(state, source="website")
