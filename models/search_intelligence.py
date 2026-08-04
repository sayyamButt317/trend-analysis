from typing import List
from pydantic import BaseModel


class SearchIntelligence(BaseModel):
    company_name: str
    search_queries: List[str]
    search_keywords: List[str]
    industry_terms: List[str]
    product_terms: List[str]
    audience_terms: List[str]
    alternative_names: List[str]
    competitor_patterns: List[str]
    excluded_terms: List[str]
    confidence: float