import logging

from agents.competitor.node.DiscoverCompetitors import DiscoverCompetitorsNode
from agents.trend.Nodes.AnalyzeCompanySocial import AnalyzeCompanySocialNode
from agents.trend.Nodes.DiscoverWebTrends import DiscoverWebTrendsNode
from agents.trend.services.instagram_discovery import (
    fetch_instagram_posts_for_usernames,
    fetch_seed_influencers,
)
from agents.trend.state.trend_state import TrendState

logger = logging.getLogger(__name__)


def _reset_discovery_state(state: TrendState) -> None:
    state["discovered_influencers"] = []
    state["discovered_posts"] = []
    state["raw_posts"] = []


def _is_company_mode(config: dict) -> bool:
    return config.get("agent_mode") == "company_trend" or bool(
        config.get("company") or config.get("company_name") or config.get("company_profile")
    )


def _is_global_mode(config: dict) -> bool:
    return config.get("agent_mode") == "global_trend"


async def DiscoverContentNode(state: TrendState) -> TrendState:
    config = state.get("config") or {}
    platform = (config.get("platform") or "instagram").lower()

    if platform != "instagram":
        state["error"] = f"Unsupported platform: {platform}. Only instagram is enabled in v1."
        _reset_discovery_state(state)
        return state

    if _is_global_mode(config):
        return await DiscoverWebTrendsNode(state)

    if _is_company_mode(config):
        logger.info(
            "Company trend mode: analyzing company social + discovering competitors for %s in %s",
            config.get("company_name") or (config.get("company") or {}).get("name") or "company",
            config.get("region") or (config.get("filters") or {}).get("region"),
        )
        state = await AnalyzeCompanySocialNode(state)
        return await DiscoverCompetitorsNode(state)

    try:
        usernames, discovered_influencers, discovery_source = await fetch_seed_influencers(
            country=config.get("country"),
            categories=[config["category"]] if config.get("category") else None,
            limit=int(config.get("influencer_limit") or 20),
            seed_usernames=config.get("seed_usernames"),
            auto_discover=config.get("auto_discover", True),
            use_database=config.get("use_database", False),
        )
    except Exception:
        logger.exception("Failed to fetch seed influencers for country=%s", config.get("country"))
        state["error"] = "Influencer discovery failed due to an internal error. Check server logs."
        _reset_discovery_state(state)
        return state

    if not usernames:
        state["error"] = (
            "No Instagram accounts found. Send an empty body for global trends today, "
            "or provide company_data + region for niche trends."
        )
        _reset_discovery_state(state)
        return state

    config["discovery_source"] = discovery_source
    state["config"] = config
    state["discovered_influencers"] = discovered_influencers

    influencer_map = {
        item["username"]: item for item in discovered_influencers if item.get("username")
    }

    try:
        posts = await fetch_instagram_posts_for_usernames(
            usernames,
            influencer_by_username=influencer_map,
            delay_seconds=float(config.get("request_delay_seconds") or 1.0),
        )
    except Exception:
        logger.exception("Failed to fetch Instagram posts")
        state["discovered_posts"] = []
        state["raw_posts"] = []
        return state

    if not posts:
        state["error"] = "Accounts were found but Instagram posts could not be fetched."
        state["discovered_posts"] = []
        state["raw_posts"] = []
        return state

    state["discovered_posts"] = posts
    state["raw_posts"] = posts
    return state
