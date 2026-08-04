import re
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from agents.trend.services.company_profile_parser import (
    merge_company_with_profile,
    normalize_profile_text,
)

INSTAGRAM_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/([A-Za-z0-9._]{2,30})/?",
    re.I,
)
LINKEDIN_URL_RE = re.compile(
    r"(?:https?://)?(?:[\w.]+)\.?linkedin\.com/(company|in)/([A-Za-z0-9_-]+)/?",
    re.I,
)


def normalize_instagram_handle(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    url_match = INSTAGRAM_URL_RE.search(text)
    if url_match:
        return url_match.group(1).lower()
    handle = text.lstrip("@").split("?")[0].strip("/").lower()
    return handle or None


def normalize_linkedin_handle(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    text = value.strip().rstrip("/")
    url_match = LINKEDIN_URL_RE.search(text)
    if url_match:
        kind, slug = url_match.group(1).lower(), url_match.group(2)
        url = f"https://www.linkedin.com/{kind}/{slug}/"
        return url, slug
    slug = text.lstrip("@").split("?")[0].strip("/")
    if not slug:
        return None, None
    return f"https://www.linkedin.com/company/{slug}/", slug


class NicheTrendRequest(BaseModel):
    company_data: str = Field(
        ...,
        min_length=20,
        description="Company DNA: services, positioning, ideal clients, differentiators.",
    )
    region: str = Field(
        ...,
        description="Target region for niche competitor and trend discovery.",
        examples=["GCC", "MENA", "United States", "United Arab Emirates"],
    )
    instausername: Optional[str] = Field(
        default=None,
        description="Company Instagram @handle or profile URL.",
        examples=["techtimize", "https://www.instagram.com/techtimize/"],
    )
    linkedinusername: Optional[str] = Field(
        default=None,
        description="LinkedIn company slug, profile slug, or full URL.",
        examples=["techtimize", "https://www.linkedin.com/company/techtimize/"],
    )
    competitors: Optional[list[str]] = Field(
        default=None,
        description="Optional competitor names or @handles.",
    )
    competitor_limit: int = Field(default=10, ge=1, le=30)
    post_limit: int = Field(default=15, ge=1, le=25)
    request_delay_seconds: float = Field(default=1.0, ge=0, le=10)
    min_engagement_rate: float = Field(default=1.0, ge=0)
    include_web_trends: bool = Field(
        default=True,
        description="Enrich niche results with filtered web trend signals.",
    )

    @field_validator("company_data", "region")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        text = normalize_profile_text(value)
        if not text:
            raise ValueError("value cannot be empty")
        return text

    @field_validator("instausername")
    @classmethod
    def _normalize_insta(cls, value: str | None) -> str | None:
        return normalize_instagram_handle(value)

    @field_validator("linkedinusername")
    @classmethod
    def _normalize_linkedin(cls, value: str | None) -> str | None:
        if not value:
            return None
        return value.strip()

    @field_validator("competitors")
    @classmethod
    def _normalize_competitors(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [item.strip() for item in value if (item or "").strip()]
        return cleaned or None

    def social_handle_overrides(self) -> dict[str, str | None]:
        linkedin_url, linkedin_username = normalize_linkedin_handle(self.linkedinusername)
        instagram_username = self.instausername
        overrides: dict[str, str | None] = {
            "instagram_username": instagram_username,
            "linkedin_url": linkedin_url,
            "linkedin_username": linkedin_username,
        }
        if instagram_username:
            overrides["instagram_url"] = f"https://www.instagram.com/{instagram_username}/"
        return overrides

    def normalized_company(self) -> dict[str, Any]:
        company = merge_company_with_profile({"profile": self.company_data})
        overrides = self.social_handle_overrides()
        for key, value in overrides.items():
            if value:
                company[key] = value
        signals = dict(company.get("company_signals") or {})
        if overrides.get("instagram_username"):
            signals["instagram_username"] = overrides["instagram_username"]
            signals["instagram_url"] = overrides.get("instagram_url")
        if overrides.get("linkedin_url"):
            signals["linkedin_url"] = overrides["linkedin_url"]
            signals["linkedin_username"] = overrides.get("linkedin_username")
        company["company_signals"] = signals
        return company

    def to_agent_config(self) -> dict[str, Any]:
        company = self.normalized_company()
        overrides = self.social_handle_overrides()
        filters: dict[str, Any] = {
            "region": self.region,
            "competitor_limit": self.competitor_limit,
            "post_limit": self.post_limit,
            "request_delay_seconds": self.request_delay_seconds,
            "keywords": list(company.get("extracted_keywords") or []),
        }
        if self.competitors:
            filters["competitors"] = self.competitors

        if company.get("flagship_services"):
            filters["industry"] = company["flagship_services"][0]
        elif company.get("services"):
            filters["industry"] = company["services"][0]

        detected_category = filters.get("industry") or company.get("name")

        return {
            "agent_mode": "niche_trend",
            "platform": "instagram",
            "include_web_trends": self.include_web_trends,
            "company": company,
            "company_name": company.get("name"),
            "company_description": company.get("description"),
            "company_profile": company.get("profile") or self.company_data,
            "company_signals": company.get("company_signals") or {},
            "detected_category": detected_category,
            "category": detected_category,
            "region": self.region,
            "min_engagement_rate": self.min_engagement_rate,
            "instagram_username": overrides.get("instagram_username") or company.get("instagram_username"),
            "instagram_url": overrides.get("instagram_url") or company.get("instagram_url"),
            "linkedin_url": overrides.get("linkedin_url") or company.get("linkedin_url"),
            "linkedin_username": overrides.get("linkedin_username") or company.get("linkedin_username"),
            "company_username": overrides.get("instagram_username") or company.get("instagram_username"),
            "filters": filters,
            **filters,
        }
