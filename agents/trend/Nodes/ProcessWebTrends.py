import logging
from agents.trend.services.web_trend_crawler import crawl_instagram_web_trends
from agents.trend.services.web_trend_parser import attach_google_trends_by_country, filter_for_niche, merge_parsed_results
from agents.trend.state.trend_state import TrendState

logger = logging.getLogger(__name__)


def _niche_keywords(config: dict) -> list[str]:
    company = config.get("company") or {}
    keywords = list(config.get("keywords") or (config.get("filters") or {}).get("keywords") or [])
    for item in (
        company.get("extracted_keywords")
        or company.get("flagship_services")
        or company.get("services")
        or []
    ):
        if item and item not in keywords:
            keywords.append(str(item))
    industry = config.get("industry") or config.get("detected_category") or config.get("category")
    if industry:
        keywords.append(str(industry))
    return keywords[:12]


async def ProcessWebTrendsNode(state: TrendState) -> TrendState:
    config = state.get("config") or {}
    region = config.get("region") or (config.get("filters") or {}).get("region")
    crawl = state.get("web_crawl") or await crawl_instagram_web_trends(region=region)

    if not crawl.get("success"):
        if config.get("agent_mode") == "global_trend":
            state["error"] = crawl.get("error") or "Web trend crawl failed."
        return state

    merged = merge_parsed_results(crawl.get("parsed_pages") or [])
    merged = attach_google_trends_by_country(
        merged,
        (crawl.get("google_trends_by_country") or {}),
    )
    if config.get("agent_mode") in {"company_trend", "niche_trend"}:
        merged = filter_for_niche(merged, _niche_keywords(config))

    state["web_crawl"] = crawl
    state["web_trends"] = merged
    state["viral_categories"] = [
        {
            "category": item.get("name"),
            "source": item.get("source"),
            "type": "reel_format",
        }
        for item in merged.get("reel_formats") or []
    ]

    existing_tags = {item.get("hashtag") for item in state.get("hashtags") or []}
    web_hashtags = [
        item for item in merged.get("hashtags") or [] if item.get("hashtag") not in existing_tags
    ]
    state["hashtags"] = (state.get("hashtags") or []) + web_hashtags

    existing_topics = {item.get("topic") for item in state.get("topics") or []}
    web_topics = [
        {"topic": item.get("topic") or item.get("key"), **item}
        for item in merged.get("topics") or []
        if (item.get("topic") or item.get("key")) not in existing_topics
    ]
    state["topics"] = (state.get("topics") or []) + web_topics

    existing_scores = state.get("trend_scores") or []
    web_scores = merged.get("trend_scores") or []
    state["trend_scores"] = sorted(
        existing_scores + web_scores,
        key=lambda item: float(item.get("trend_score") or 0),
        reverse=True,
    )

    config["web_sources"] = crawl.get("sources") or []
    state["config"] = config
    logger.info(
        "Web trends merged: %s hashtags, %s reel formats from %s sources",
        len(merged.get("hashtags") or []),
        len(merged.get("reel_formats") or []),
        len(crawl.get("sources") or []),
    )
    for entry in merged.get("source_breakdown") or []:
        counts = entry.get("counts") or {}
        logger.info(
            "  %s: %s items (topics=%s, hashtags=%s, formats=%s)",
            entry.get("source"),
            counts.get("total"),
            counts.get("topics"),
            counts.get("hashtags"),
            counts.get("reel_formats"),
        )
    return state
