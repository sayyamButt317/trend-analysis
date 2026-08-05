from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    title: str
    url: str
    content: str
    score: float


class DiscoveryCandidate(BaseModel):

    company_name: str
    website: str
    title: str
    description: str
    source_query: str
    tavily_score: float
    social_links: dict[str, str] = Field(default_factory=dict)