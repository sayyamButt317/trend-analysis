
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator


class CompanyInput(BaseModel):
    name: str = Field(..., description="Company name")
    website: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    profile_text: Optional[str] = None

    @field_validator("website", mode="before")
    @classmethod
    def _normalize_website(cls, value: Any) -> Optional[str]:
        if value is None or value == "":
            return None
        return str(value).strip()


class CompanyProfile(BaseModel):
    name: str
    website: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    category: Optional[str] = None
    niche: Optional[str] = None
    business_model: Optional[str] = None
    pricing_model: Optional[str] = None
    target_audience: List[str] = Field(default_factory=list)
    products: List[str] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)
    features: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    positioning: Optional[str] = None
    value_proposition: Optional[str] = None
    countries: List[str] = Field(default_factory=list)
    competitors_hint: List[str] = Field(default_factory=list)
    country: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    confidence: float = 0.0
    embeddings: List[float] = Field(default_factory=list)
    source: str = "heuristic"

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class CompanySummary(BaseModel):
    linkedin_url: Optional[str] = None
    name: Optional[str] = None
    followers: Optional[str] = None


class Employee(BaseModel):
    name: str
    designation: Optional[str] = None
    linkedin_url: Optional[str] = None


class LinkedInCompany(BaseModel):
    linkedin_url: str
    name: Optional[str] = None
    about_us: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    headquarters: Optional[str] = None
    founded: Optional[str] = None
    industry: Optional[str] = None
    company_type: Optional[str] = None
    company_size: Optional[str] = None
    specialties: Optional[str] = None
    headcount: Optional[int] = None
    showcase_pages: List[CompanySummary] = Field(default_factory=list)
    affiliated_companies: List[CompanySummary] = Field(default_factory=list)
    employees: List[Employee] = Field(default_factory=list)

    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin_url(cls, value: str) -> str:
        if "linkedin.com/company/" not in value:
            raise ValueError("Must be a valid LinkedIn company URL (contains /company/)")
        return value

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


Company = LinkedInCompany
