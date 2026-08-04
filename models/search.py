from pydantic import BaseModel
from typing import List


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