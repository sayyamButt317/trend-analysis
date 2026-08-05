from typing import Any, Optional
import re

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from agents.trend.services.company_profile_parser import (
    merge_company_with_profile,
    normalize_profile_text,
)
from core.runtime import runtime_profile
from scrapper.instagram_finder.validator import is_valid_instagram_username


SUPPORTED_MEDIA_TYPES = ("Reels", "Carousel", "Image", "Video")

LINKEDIN_URL_RE = re.compile(
    r"(?:https?://)?(?:[\w.]+)\.?linkedin\.com/(company|in)/([A-Za-z0-9_-]+)/?",
    re.I,
)


def normalize_instagram_username(value: str | None) -> str | None:
    if not value:
        return None
    handle = value.strip().lstrip("@").lower()
    if not handle or not is_valid_instagram_username(handle):
        return None
    return handle


def normalize_linkedin_url(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if "linkedin.com" in text.lower():
        match = LINKEDIN_URL_RE.search(text if text.startswith("http") else f"https://{text.lstrip('www.')}")
        if match:
            kind, slug = match.group(1).lower(), match.group(2)
            return f"https://www.linkedin.com/{kind}/{slug}/"
        return text if text.startswith("http") else f"https://{text}"
    slug = text.strip("/")
    return f"https://www.linkedin.com/company/{slug}/"


class CompetitorFilters(BaseModel):
    region: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    industry: Optional[str] = None
    category: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    competitor_usernames: list[str] = Field(default_factory=list)
    exclude_usernames: list[str] = Field(default_factory=list)
    competitor_limit: int = Field(default=10, ge=1, le=50)
    post_limit: int = Field(default=10, ge=1, le=25)
    media_types: list[str] = Field(default_factory=list)
    min_followers: Optional[int] = Field(default=None, ge=0)
    request_delay_seconds: float = Field(default=1.0, ge=0, le=10)


class CompetitorAnalysisRequest(BaseModel):
    """Analyze your business (optionally via IG/LinkedIn) then discover competitors."""

    model_config = ConfigDict(populate_by_name=True)

    company_data: str = Field(
        ...,
        min_length=20,
        description="Full company details text (services, team, positioning, ideal clients, etc.)",
        examples=[
            "Techtimize LLC is a US-registered IT company founded in 2023. "
            "Services: AI Development, Web Application Development, Staff Augmentation..."
        ],
    )
    region: str = Field(
        ...,
        min_length=2,
        description="Target region to find competitors in",
        examples=["GCC", "MENA", "North America", "Europe", "United Arab Emirates"],
    )
    instagram_username: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("instagram_username", "instausername"),
        serialization_alias="instagram_username",
        description="Your company's Instagram @handle — used to analyze your content before finding competitors.",
        examples=["techtimize"],
    )
    company_name: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("company_name", "companyname"),
        serialization_alias="company_name",
        description="Your company name — used to build the LinkedIn posts URL dynamically.",
        examples=["Techtimize"],
    )
    linkedin_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("linkedin_url", "linkedinurl"),
        serialization_alias="linkedin_url",
        description="Optional LinkedIn override. By default the posts URL is built from company_name.",
        examples=["https://www.linkedin.com/company/techtimize/"],
    )
    competitors: Optional[list[str]] = Field(
        default=None,
        description=(
            "Optional list of competitor names or Instagram handles (@user). "
            "When provided, analysis runs only on these accounts and skips auto-discovery."
        ),
        examples=[["@competitor1", "Acme Software Lahore"]],
    )
    competitor_limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=50,
        description="Max competitors to analyze (from request; default 10).",
    )
    post_limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=25,
        description="Instagram posts per account (default 10).",
    )

    @field_validator("company_data", "region")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        text = normalize_profile_text(value)
        if not text:
            raise ValueError("Value cannot be empty")
        return text

    @field_validator("instagram_username")
    @classmethod
    def _normalize_instagram(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_instagram_username(value)
        if not normalized:
            raise ValueError("Invalid Instagram username")
        return normalized

    @field_validator("company_name")
    @classmethod
    def _normalize_company_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            raise ValueError("Company name cannot be empty")
        return text

    @field_validator("linkedin_url")
    @classmethod
    def _normalize_linkedin(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_linkedin_url(value)
        if not normalized:
            raise ValueError("Invalid LinkedIn URL")
        return normalized

    @field_validator("competitors")
    @classmethod
    def _normalize_competitors(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [item.strip() for item in value if (item or "").strip()]
        return cleaned or None

    def _company_with_socials(self) -> dict[str, Any]:
        extras: dict[str, Any] = {}
        if self.company_name:
            extras["name"] = self.company_name
        if self.instagram_username:
            extras["instagram_username"] = self.instagram_username
            extras["instagram_url"] = f"https://www.instagram.com/{self.instagram_username}/"
        if self.linkedin_url:
            extras["linkedin_url"] = self.linkedin_url
            match = LINKEDIN_URL_RE.search(self.linkedin_url)
            if match:
                extras["linkedin_username"] = match.group(2)
        return merge_company_with_profile({"profile": self.company_data, **extras})

    def to_agent_config(self) -> dict[str, Any]:
        company = self._company_with_socials()
        profile = runtime_profile()
        competitor_limit = int(
            self.competitor_limit
            if self.competitor_limit is not None
            else profile.get("competitor_limit") or 10
        )
        post_limit = self.post_limit or profile["post_limit"]
        exclude_usernames: list[str] = []
        if company.get("instagram_username"):
            exclude_usernames.append(company["instagram_username"])

        company_name = (self.company_name or company.get("name") or "").strip()
        if company_name:
            company["name"] = company_name

        filters = CompetitorFilters(
            region=self.region,
            competitor_limit=competitor_limit,
            post_limit=post_limit,
            request_delay_seconds=float(profile["request_delay_seconds"]),
            exclude_usernames=exclude_usernames,
        ).model_dump()
        if self.competitors:
            filters["competitors"] = self.competitors
        filters["keywords"] = list(
            dict.fromkeys([*(filters.get("keywords") or []), *(company.get("extracted_keywords") or [])])
        )

        if company.get("flagship_services"):
            filters["industry"] = company["flagship_services"][0]
        elif company.get("services"):
            filters["industry"] = company["services"][0]

        return {
            "company": company,
            "company_name": company_name or company.get("name"),
            "company_username": company.get("instagram_username"),
            "company_description": company.get("description"),
            "company_profile": company.get("profile") or self.company_data,
            "company_website": company.get("website"),
            "company_signals": company.get("company_signals") or {},
            "company_instagram_username": company.get("instagram_username"),
            "company_linkedin_url": company.get("linkedin_url"),
            "analyze_company_social": bool(
                company.get("instagram_username") or company_name or company.get("linkedin_url")
            ),
            "runtime_profile": profile,
            "skip_linkedin": profile["skip_linkedin"],
            "skip_playwright": profile["skip_playwright"],
            **filters,
            "filters": filters,
        }

    def normalized_company(self) -> dict[str, Any]:
        return self._company_with_socials()
