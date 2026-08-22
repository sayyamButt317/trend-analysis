from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlparse

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from agents.trend.schemas.competitor_request import (
    normalize_instagram_username,
    normalize_linkedin_url,
)
from agents.trend.services.company_profile_parser import (
    merge_company_with_profile,
    normalize_profile_text,
)
from core.runtime import runtime_profile


def normalize_website_url(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if not re.match(r"^https?://", text, re.I):
        text = f"https://{text.lstrip('/')}"
    parsed = urlparse(text)
    if not parsed.netloc or "." not in parsed.netloc:
        raise ValueError("Invalid website URL")
    # Keep path if meaningful, drop trailing slash on bare domains.
    if parsed.path in {"", "/"} and not parsed.query:
        return f"{parsed.scheme}://{parsed.netloc}".lower()
    return text.rstrip("/")


class AnalyzeCompanyRequest(BaseModel):
    """Analyze a company from website URL (+ optional profile text / socials)."""

    model_config = ConfigDict(populate_by_name=True)

    website_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("website_url", "websiteurl", "website"),
        serialization_alias="website_url",
        description="Company website URL to crawl and analyze (primary input).",
        examples=["https://techtimize.co", "techtimize.co"],
    )
    company_data: Optional[str] = Field(
        default=None,
        description=(
            "Optional extra company details text. If omitted, analysis is driven by "
            "website crawl (+ Instagram/LinkedIn if provided)."
        ),
    )
    region: Optional[str] = Field(
        default=None,
        description="Optional operating / target region",
        examples=["Pakistan", "GCC", "North America"],
    )
    company_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("company_id", "companyId"),
        serialization_alias="company_id",
        description="External company identifier to link this analysis run in your system.",
        examples=["550e8400-e29b-41d4-a716-446655440000", "org_12345"],
    )
    instagram_username: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("instagram_username", "instausername"),
    )
    linkedin_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("linkedin_url", "linkedinurl"),
    )
    post_limit: Optional[int] = Field(default=None, ge=1, le=25)

    @field_validator("website_url")
    @classmethod
    def _normalize_website(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_website_url(value)

    @field_validator("company_data")
    @classmethod
    def _strip_company_data(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = normalize_profile_text(value)
        return text or None

    @field_validator("region", "company_id")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        return text or None

    @field_validator("instagram_username")
    @classmethod
    def _normalize_instagram(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_instagram_username(value)
        if not normalized:
            raise ValueError("Invalid Instagram username")
        return normalized

    @field_validator("linkedin_url")
    @classmethod
    def _normalize_linkedin(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_linkedin_url(value)
        if not normalized:
            raise ValueError("Invalid LinkedIn URL")
        return normalized

    @model_validator(mode="after")
    def _require_website_or_company_data(self) -> "AnalyzeCompanyRequest":
        has_website = bool(self.website_url)
        has_data = bool(self.company_data and len(self.company_data.strip()) >= 20)
        if not has_website and not has_data:
            raise ValueError(
                "Provide website_url and/or company_data (min 20 chars) to analyze the company"
            )
        return self

    def _company_with_socials(self) -> dict[str, Any]:
        extras: dict[str, Any] = {}
        if self.website_url:
            extras["website"] = self.website_url
        if self.instagram_username:
            extras["instagram_username"] = self.instagram_username
            extras["instagram_url"] = f"https://www.instagram.com/{self.instagram_username}/"
        if self.linkedin_url:
            extras["linkedin_url"] = self.linkedin_url
        if self.region:
            extras["region"] = self.region

        profile_text = self.company_data or (
            f"Analyze company from website {self.website_url}."
            if self.website_url
            else ""
        )

        return merge_company_with_profile({"profile": profile_text, **extras})

    def to_agent_config(self) -> dict[str, Any]:
        company = self._company_with_socials()
        profile = runtime_profile()
        post_limit = self.post_limit or profile.get("post_limit") or 10
        if self.website_url:
            company["website"] = self.website_url

        filters = {
            "region": self.region,
            "post_limit": post_limit,
            "exclude_usernames": (
                [company["instagram_username"]] if company.get("instagram_username") else []
            ),
        }
        return {
            "company": company,
            "company_id": self.company_id,
            "company_name": company.get("name"),
            "company_username": company.get("instagram_username"),
            "company_description": company.get("description") or self.company_data,
            "company_profile": company.get("profile") or self.company_data,
            "company_website": self.website_url or company.get("website"),
            "website_url": self.website_url or company.get("website"),
            "company_signals": company.get("company_signals") or {},
            "company_instagram_username": company.get("instagram_username"),
            "company_linkedin_url": company.get("linkedin_url"),
            "analyze_company_social": bool(
                company.get("instagram_username") or company.get("name") or company.get("linkedin_url")
            ),
            "runtime_profile": profile,
            "skip_linkedin": profile.get("skip_linkedin"),
            "skip_playwright": profile.get("skip_playwright"),
            "post_limit": post_limit,
            "region": self.region,
            "filters": filters,
        }

    def normalized_company(self) -> dict[str, Any]:
        return self._company_with_socials()
