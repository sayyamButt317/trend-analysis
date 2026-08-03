from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from agents.trend.services.company_profile_parser import (
    merge_company_with_profile,
    normalize_profile_text,
)


class TrendDiscoveryRequest(BaseModel):

    company_data: Optional[str] = Field(
        default=None,
        description="Optional company profile. When provided with region, finds niche-specific trends.",
    )
    instausername: Optional[str] = Field(
        default=None,
        description="Optional Instagram username. When provided with region, finds niche-specific trends.",
    )
    linkedinusername: Optional[str] = Field(
        default=None,
        description="Optional LinkedIn username. When provided with region, finds niche-specific trends.",
    )
    xusername: Optional[str] = Field(
        default=None,
        description="Optional X username. When provided with region, finds niche-specific trends.",
    )
    facebookusername: Optional[str] = Field(
        default=None,
        description="Optional Facebook username. When provided with region, finds niche-specific trends.",
    )
    redditusername: Optional[str] = Field(
        default=None,
        description="Optional Reddit username. When provided with region, finds niche-specific trends.",
    )
    xusername: Optional[str] = Field(
        default=None,
        description="Optional X username. When provided with region, finds niche-specific trends.",
    )
    region: Optional[str] = Field(
        default=None,
        description="Target region (required when company_data is provided).",
        examples=["GCC", "MENA", "United States", "United Arab Emirates"],
    )
    competitors: Optional[list[str]] = Field(
        default=None,
        description="Optional competitor names or @handles for company mode.",
    )
    competitor_limit: int = Field(default=10, ge=1, le=30)
    post_limit: int = Field(default=15, ge=1, le=25)
    request_delay_seconds: float = Field(default=1.0, ge=0, le=10)
    min_engagement_rate: float = Field(default=1.0, ge=0)
    include_web_trends: bool = Field(
        default=True,
        description="Enrich results by crawling trend websites (SocialBee, Metricool, etc.).",
    )

    @field_validator("company_data")
    @classmethod
    def _strip_company(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = normalize_profile_text(value)
        return text or None

    @field_validator("region")
    @classmethod
    def _strip_region(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = normalize_profile_text(value)
        return text or None

    @field_validator("competitors")
    @classmethod
    def _normalize_competitors(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [item.strip() for item in value if (item or "").strip()]
        return cleaned or None

    @model_validator(mode="after")
    def _validate_mode_fields(self) -> "TrendDiscoveryRequest":
        has_company = bool(self.company_data)
        has_region = bool(self.region)
        if has_company and not has_region:
            raise ValueError("region is required when company_data is provided")
        if has_region and not has_company:
            raise ValueError("company_data is required when region is provided")
        if has_company and self.company_data and len(self.company_data) < 20:
            raise ValueError("company_data must be at least 20 characters")
        return self

    @property
    def mode(self) -> str:
        return "company_trend" if self.company_data and self.region else "global_trend"

    def normalized_company(self) -> dict[str, Any]:
        if not self.company_data:
            return {}
        return merge_company_with_profile({"profile": self.company_data})

    def to_agent_config(self) -> dict[str, Any]:
        if self.mode == "global_trend":
            return {
                "agent_mode": "global_trend",
                "platform": "instagram",
                "include_web_trends": self.include_web_trends,
                "min_engagement_rate": self.min_engagement_rate,
            }

        company = self.normalized_company()
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
            "agent_mode": "company_trend",
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
            "filters": filters,
            **filters,
        }
