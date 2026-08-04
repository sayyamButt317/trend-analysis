from pydantic import BaseModel, Field


class WebsiteIntelligence(BaseModel):
    url: str = ""
    company_name: str = ""
    description: str = ""
    products: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    pricing_model: str = ""
    industries: list[str] = Field(default_factory=list)
    target_audience: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    business_model: str = ""
    positioning: str = ""
    competitors: list[str] = Field(default_factory=list)
    social_links: dict[str, str] = Field(default_factory=dict)
    confidence: float = 0.0
    raw_markdown: str = ""
