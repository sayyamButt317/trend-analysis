import logging

from agents.trend.services.instagram_discovery import (
    fetch_instagram_posts_for_usernames,
    fetch_seed_influencers,
)
from agents.trend.state.trend_state import TrendState

logger = logging.getLogger(__name__)


def _reset_discovery_state(state: TrendState) -> None:
    """Ensure no stale/partial data survives an error branch."""
    state["discovered_influencers"] = []
    state["discovered_posts"] = []
    state["raw_posts"] = []


async def DiscoverContentNode(state: TrendState) -> TrendState:
    config = state.get("config") or {}
    platform = (config.get("platform") or "instagram").lower()

    if platform != "instagram":
        state["error"] = f"Unsupported platform: {platform}. Only instagram is enabled in v1."
        _reset_discovery_state(state)
        return state

    # --- Step 1: discover seed influencers ---
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
        category_hint = f" in {config.get('category')}" if config.get("category") else ""
        state["error"] = (
            f"No Instagram influencers found via live search{category_hint}. "
            "Try United Arab Emirates or Saudi Arabia with a supported category: "
            "Fashion, Beauty, Fitness, Food, Travel, Luxury, Lifestyle."
        )
        _reset_discovery_state(state)
        return state

    config["discovery_source"] = discovery_source
    state["config"] = config
    state["discovered_influencers"] = discovered_influencers

    logger.info(
        "Discovering Instagram content from %s influencer(s) via %s",
        len(usernames),
        discovery_source,
    )

    influencer_map = {
        item["username"]: item for item in discovered_influencers if item.get("username")
    }

    # --- Step 2: fetch posts for discovered influencers ---
    try:
        posts = await fetch_instagram_posts_for_usernames(
            usernames,
            influencer_by_username=influencer_map,
            delay_seconds=float(config.get("request_delay_seconds") or 1.0),
        )
    except Exception:
        logger.exception("Failed to fetch Instagram posts for usernames=%s", usernames)
        state["error"] = "Instagram post fetching failed due to an internal error. Check server logs."
        state["discovered_posts"] = []
        state["raw_posts"] = []
        return state

    logger.info(
        "Collected %s posts from %s influencer(s)",
        len(posts),
        len(usernames),
    )

    if not posts:
        state["error"] = (
            "Influencers were found but Instagram post media could not be fetched. "
            "Check server logs for 'Instagram trend fetch failed for @username' lines and retry."
        )
        state["discovered_posts"] = []
        state["raw_posts"] = []
        return state

    state["discovered_posts"] = posts
    state["raw_posts"] = posts
    return state