from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from agents.trend.services.company_profile_parser import (
    merge_company_with_profile,
    normalize_profile_text,
)
from core.runtime import runtime_profile


SUPPORTED_MEDIA_TYPES = ("Reels", "Carousel", "Image", "Video")


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
    competitor_limit: int = Field(default=50, ge=1, le=50)
    post_limit: int = Field(default=10, ge=1, le=25)
    media_types: list[str] = Field(default_factory=list)
    min_followers: Optional[int] = Field(default=None, ge=0)
    request_delay_seconds: float = Field(default=1.0, ge=0, le=10)


class CompetitorAnalysisRequest(BaseModel):
    """Simple request: paste company details + pick a region."""

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
        description=(
            "Max competitors to analyze. Defaults to 5 on Vercel/serverless and 50 locally. "
            "Use 3–5 on serverless to stay under the 300s timeout."
        ),
    )
    post_limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=25,
        description="Instagram posts per competitor (default 5 on serverless, 10 locally).",
    )

    @field_validator("company_data", "region")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        text = normalize_profile_text(value)
        if not text:
            raise ValueError("Value cannot be empty")
        return text

    @field_validator("competitors")
    @classmethod
    def _normalize_competitors(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [item.strip() for item in value if (item or "").strip()]
        return cleaned or None

    def to_agent_config(self) -> dict[str, Any]:
        company = merge_company_with_profile({"profile": self.company_data})
        profile = runtime_profile()
        competitor_limit = self.competitor_limit or profile["competitor_limit"]
        post_limit = self.post_limit or profile["post_limit"]
        filters = CompetitorFilters(
            region=self.region,
            competitor_limit=competitor_limit,
            post_limit=post_limit,
            request_delay_seconds=float(profile["request_delay_seconds"]),
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
            "company_name": company.get("name"),
            "company_username": company.get("instagram_username"),
            "company_description": company.get("description"),
            "company_profile": company.get("profile") or self.company_data,
            "company_website": company.get("website"),
            "company_signals": company.get("company_signals") or {},
            "runtime_profile": profile,
            "skip_linkedin": profile["skip_linkedin"],
            "skip_playwright": profile["skip_playwright"],
            **filters,
            "filters": filters,
        }

    def normalized_company(self) -> dict[str, Any]:
        return merge_company_with_profile({"profile": self.company_data})
