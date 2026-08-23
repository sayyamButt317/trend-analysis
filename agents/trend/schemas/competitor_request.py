from typing import Any, Optional
import re
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator
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
    model_config = ConfigDict(populate_by_name=True)
    company_data: Optional[str] = Field(
        default=None,
        description=(
            "Full company details text. Required unless you pass structured `company` "
            "from POST /analyze-company/analyze."
        ),
        examples=[
            "Acme Health is a clinic network offering telemedicine and diagnostics in Dubai. "
            "Services: general practice, lab tests, home visits..."
        ],
    )
    company: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "Structured company object from POST /analyze-company/analyze (`company` field). "
            "Pass with `summary_text` and/or `company_analysis` to skip re-crawling your "
            "website / Instagram / LinkedIn."
        ),
    )
    summary_text: Optional[str] = Field(
        default=None,
        description="Company DNA narrative from analyze-company (top-level `summary_text`).",
    )
    company_analysis: Optional[dict[str, Any]] = Field(
        default=None,
        description="Slim platform analysis from analyze-company (`company_analysis` field).",
    )
    executive_snapshot: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional intelligence block from analyze-company.",
    )
    digital_presence: Optional[dict[str, Any]] = None
    market_position: Optional[dict[str, Any]] = None
    positioning_analysis: Optional[dict[str, Any]] = None
    strengths_and_weaknesses: Optional[dict[str, Any]] = None
    growth_opportunities: Optional[list[Any]] = None
    recommended_actions: Optional[list[Any]] = None
    region: str = Field(
        ...,
        min_length=2,
        description="Target region to find competitors in",
        examples=["GCC", "MENA", "North America", "Europe", "United Arab Emirates", "Pakistan"],
    )
    instagram_username: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("instagram_username", "instausername"),
        serialization_alias="instagram_username",
        description="Your company's Instagram @handle — used to analyze your content before finding competitors.",
        examples=["acmehealth"],

    )
    company_name: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("company_name", "companyname"),
        serialization_alias="company_name",
        description="Your company name — used to build the LinkedIn posts URL dynamically.",
        examples=["Acme Health"],

    )
    linkedin_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("linkedin_url", "linkedinurl"),
        serialization_alias="linkedin_url",
        description="Optional LinkedIn override. By default the posts URL is built from company_name.",
        examples=["https://www.linkedin.com/company/acme-health/"],
    )
    competitors: Optional[list[str]] = Field(
        default=None,
        description=(
            "Optional competitors. Mix any of: Instagram @handles, LinkedIn company URLs, "
            "company website URLs, or company names. When provided, those competitors are used "
            "and auto-discovery is skipped. Omit to auto-discover authentic peers from company DNA + region."
        ),
        examples=[
            [
                "@confiz",
                "https://www.linkedin.com/company/systems-limited/",
                "https://venturedive.com",
                "VentureDive",
            ]
        ],
    )
    competitor_limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=50,
        description=(
            "Max competitors to analyze. Optional. "
            "If you provide `competitors`, defaults to that list length (analyzes all of them). "
            "If auto-discovering, defaults to 10."
        ),
    )
    post_limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=25,
        description="Instagram posts per account (default 10).",
    )


    @field_validator("company_data", "summary_text")
    @classmethod
    def _strip_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = normalize_profile_text(value)
        return text or None

    @field_validator("region")
    @classmethod
    def _strip_region(cls, value: str) -> str:
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



    def _has_company_handoff(self) -> bool:
        company = self.company or {}
        if not isinstance(company, dict) or not company:
            return False
        has_identity = bool(company.get("name") or company.get("website"))
        has_dna = bool(
            company.get("services")
            or company.get("flagship_services")
            or self.summary_text
            or self.company_analysis
        )
        return has_identity and has_dna


    @model_validator(mode="after")
    def _require_company_data_or_handoff(self) -> "CompetitorAnalysisRequest":
        has_handoff = self._has_company_handoff()
        has_data = bool(self.company_data and len(self.company_data.strip()) >= 20)
        if not has_handoff and not has_data:
            raise ValueError(
                "Provide company_data (min 20 chars) or structured company + summary_text/"
                "company_analysis from /analyze-company/analyze"
            )
        return self



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

        seed = dict(self.company or {})
        profile_text = (
            self.company_data
            or self.summary_text
            or seed.get("profile")
            or seed.get("description")
            or ""
        )

        return merge_company_with_profile(
            {
                "profile": profile_text or (seed.get("name") or "Company"),
                **seed,
                **extras,
            }
        )

    def to_agent_config(self) -> dict[str, Any]:
        company = self._company_with_socials()
        profile = runtime_profile()
        provided = list(self.competitors or [])
        if self.competitor_limit is not None:
            competitor_limit = int(self.competitor_limit)
        elif provided:
            competitor_limit = min(max(len(provided), 1), 50)
        else:
            competitor_limit = int(profile.get("competitor_limit") or 10)
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
        config: dict[str, Any] = {
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
        if self._has_company_handoff():
            config["skip_company_analysis"] = True
            if self.summary_text:
                config["summary_text"] = self.summary_text
            if self.company_analysis:
                config["company_analysis"] = self.company_analysis
            for key in (
                "executive_snapshot",
                "digital_presence",
                "market_position",
                "positioning_analysis",
                "strengths_and_weaknesses",
                "growth_opportunities",
                "recommended_actions",
            ):
                value = getattr(self, key, None)
                if value:
                    config[key] = value
        return config



    def normalized_company(self) -> dict[str, Any]:
        return self._company_with_socials()

