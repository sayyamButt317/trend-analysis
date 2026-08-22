from typing import Any, Optional, TypedDict


class WebsitePresence(TypedDict, total=False):
    score: int
    strengths: list[str]
    weaknesses: list[str]


class InstagramPresence(TypedDict, total=False):
    score: int | None
    followers: int | None
    engagement_rate: float | None
    content_strength: int | None
    audience_strength: int | None
    status: str


class LinkedInPresence(TypedDict, total=False):
    score: int | None
    status: str


class DigitalPresence(TypedDict, total=False):
    overall_score: int
    website: WebsitePresence
    instagram: InstagramPresence
    linkedin: LinkedInPresence


class ExecutiveSnapshot(TypedDict, total=False):
    company_type: str
    business_model: str
    primary_market: str
    primary_customers: list[str]
    core_offering: str
    market_position: str
    business_maturity: str
    overall_digital_presence_score: int


class MarketPosition(TypedDict, total=False):
    category: str
    position: str
    specialization: str
    service_breadth: str
    geographic_focus: str
    enterprise_focus: str
    differentiation_strength: int
    positioning_clarity: int
    assessment: str


class PositioningAnalysis(TypedDict, total=False):
    what_you_are_known_for: list[str]
    what_is_unclear: list[str]
    recommended_positioning: str


class GrowthOpportunity(TypedDict, total=False):
    priority: str
    area: str
    finding: str
    impact: str
    action: str


class RecommendedAction(TypedDict, total=False):
    priority: int
    title: str
    category: str
    impact: str
    effort: str
    action: str


class StrengthsAndWeaknesses(TypedDict, total=False):
    strengths: list[str]
    weaknesses: list[str]


class AnalyzeCompanyState(TypedDict, total=False):
    config: dict[str, Any]
    company_profile: dict[str, Any]
    company_analysis: dict[str, Any]
    company_posts: list[dict[str, Any]]
    linkedin_posts: list[dict[str, Any]]
    web_crawl: dict[str, Any]
    discovery_features: dict[str, Any]
    user_instagram: dict[str, Any]
    user_instagram_profile: dict[str, Any]
    user_instagram_analysis: dict[str, Any]
    instagram_competitor_hints: dict[str, Any]
    company_summary: dict[str, Any]
    company_summary_text: str
    # Company intelligence (post-DNA)
    executive_snapshot: ExecutiveSnapshot
    digital_presence: DigitalPresence
    market_position: MarketPosition
    positioning_analysis: PositioningAnalysis
    strengths_and_weaknesses: StrengthsAndWeaknesses
    growth_opportunities: list[GrowthOpportunity]
    recommended_actions: list[RecommendedAction]
    warnings: list[str]
    error: Optional[str]
    _meta: dict[str, Any]
