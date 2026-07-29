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

    error: Optional[str]
    _meta: dict[str, Any]
