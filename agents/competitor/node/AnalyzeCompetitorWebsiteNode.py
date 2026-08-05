import logging
from typing import Any

from agents.competitor.pipeline_log import log_event
from agents.competitor.state.competitor_state import CompetitorState
from service.Competitor.website_crawler import WebsiteCrawlerService

logger = logging.getLogger(__name__)

MAX_WEBSITE_CRAWLS = 5


async def analyze_competitor_website_node(state: CompetitorState) -> CompetitorState:
    """Crawl competitor websites (Firecrawl) and attach positioning/services intel."""
    if state.get("error"):
        return state

    config = state.get("config") or {}
    runtime = config.get("runtime_profile") or {}
    max_crawls = int(runtime.get("max_competitor_website_crawls") or MAX_WEBSITE_CRAWLS)
    if runtime.get("serverless"):
        max_crawls = min(max_crawls, 3)

    competitors = list(
        state.get("discovered_influencers") or state.get("competitors") or []
    )
    if not competitors:
        return state

    crawler = WebsiteCrawlerService()
    if not crawler.firecrawl.available:
        log_event("3_competitor_social", "Competitor website crawl skipped — FIRECRAWL_API_KEY missing")
        state["competitor_website_intel"] = []
        return state

    log_event(
        "3_competitor_social",
        "Crawling competitor websites",
        competitors=len(competitors),
        max_crawls=max_crawls,
    )
    enriched: list[dict[str, Any]] = []
    crawled = 0
    website_records: list[dict[str, Any]] = []

    for competitor in competitors:
        item = dict(competitor)
        website = (item.get("website") or "").strip()
        if website and crawled < max_crawls:
            name = item.get("name") or item.get("username") or "Competitor"
            try:
                log_event("3_competitor_social", "Crawling competitor site", name=name, url=website)
                intel = await crawler.crawl_company_website(url=website, company_name=name)
                if intel:
                    intel_dict = intel.model_dump()
                    item["website_intelligence"] = intel_dict
                    item["website_services"] = intel_dict.get("services") or []
                    item["website_keywords"] = intel_dict.get("keywords") or []
                    website_records.append(
                        {
                            "name": name,
                            "username": item.get("username"),
                            "website": website,
                            "intelligence": intel_dict,
                        }
                    )
                    crawled += 1
            except Exception:
                logger.warning("Website crawl failed for %s", website, exc_info=True)
        enriched.append(item)

    state["discovered_influencers"] = enriched
    state["competitors"] = enriched
    state["competitor_website_intel"] = website_records
    config["competitor_websites_crawled"] = crawled
    state["config"] = config

    log_event(
        "3_competitor_social",
        "Competitor website crawl finished",
        crawled=crawled,
        total=len(competitors),
    )
    return state


AnalyzeCompetitorWebsiteNode = analyze_competitor_website_node
