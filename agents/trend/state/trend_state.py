from typing import Any, Optional, TypedDict


class TrendState(TypedDict, total=False):
    config: dict[str, Any]

    discovered_posts: list[dict[str, Any]]
    raw_posts: list[dict[str, Any]]
    processed_posts: list[dict[str, Any]]

    hashtags: list[dict[str, Any]]
    audios: list[dict[str, Any]]
    topics: list[dict[str, Any]]

    engagement_metrics: list[dict[str, Any]]
    viral_posts: list[dict[str, Any]]

    trend_groups: list[dict[str, Any]]
    trend_scores: list[dict[str, Any]]

    trend_summary: str
    saved_trend_id: Optional[str]
    discovered_influencers: list[dict[str, Any]]
    viral_sounds: list[dict[str, Any]]
    viral_categories: list[dict[str, Any]]
    audio_summary: list[dict[str, Any]]
    content_mix: list[dict[str, Any]]
    competitor_summary: str

    web_crawl: dict[str, Any]
    web_trends: dict[str, Any]

    company_analysis: dict[str, Any]
    company_posts: list[dict[str, Any]]
    linkedin_posts: list[dict[str, Any]]
    pain_points: list[dict[str, Any]]

    error: Optional[str]
    _meta: dict[str, Any]

    company_profile: dict[str, Any]
    search_intelligence: dict[str, Any]
    discovery_candidates: list[dict[str, Any]]
    verified_competitors: list[dict[str, Any]]
    similarity_scores: list[dict[str, Any]]
    gap_analysis: dict[str, Any]
    recommendations: list[dict[str, Any]]
    ai_report: dict[str, Any]
