import logging
from agents.trend.services.web_trend_crawler import crawl_instagram_web_trends
from agents.trend.state.trend_state import TrendState

logger = logging.getLogger(__name__)


async def DiscoverWebTrendsNode(state: TrendState) -> TrendState:
    config = state.get("config") or {}
    config["discovery_source"] = "web_trend_crawl"
    config["agent_mode"] = "global_trend"
    state["config"] = config

    region = config.get("region") or (config.get("filters") or {}).get("region")
    crawl = await crawl_instagram_web_trends(region=region)
    state["web_crawl"] = crawl

    if not crawl.get("success"):
        state["error"] = crawl.get("error") or "Failed to crawl Instagram trend sources."
        state["discovered_influencers"] = []
        state["discovered_posts"] = []
        state["raw_posts"] = []
        return state

    state["discovered_influencers"] = [
        {"username": source, "name": source, "source": "web_trend_source"}
        for source in crawl.get("sources") or []
    ]
    state["discovered_posts"] = []
    state["raw_posts"] = []
    logger.info("Global web trend discovery fetched %s sources", len(crawl.get("sources") or []))
    return state
