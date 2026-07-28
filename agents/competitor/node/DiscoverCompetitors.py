import logging

from agents.trend.services.competitor_discovery import discover_competitors
from agents.trend.services.competitor_matcher import rank_competitors
from agents.trend.services.instagram_discovery import fetch_instagram_posts_for_usernames
from agents.trend.services.instagramuser_details import InstagramRateLimitError
from agents.trend.services.manual_competitors import resolve_manual_competitors
from agents.trend.state.trend_state import TrendState

logger = logging.getLogger(__name__)

MIN_MATCH_SCORE = 0.25
CANDIDATE_POOL_MULTIPLIER = 2


def resetDiscoveryState(state: TrendState) -> None:
    state["discovered_influencers"] = []
    state["discovered_posts"] = []
    state["raw_posts"] = []


def _manual_competitor_inputs(config: dict, filters: dict) -> list[str]:
    return (
        filters.get("competitors")
        or config.get("competitors")
        or []
    )


async def DiscoverCompetitorsNode(state: TrendState) -> TrendState:
    config = state.get("config") or {}
    company = config.get("company") or {}
    filters = config.get("filters") or config

    company_name = (company.get("name") or config.get("company_name") or "").strip()
    if not company_name:
        state["error"] = "Company name is required for competitor analysis."
        resetDiscoveryState(state)
        return state

    competitor_limit = int(filters.get("competitor_limit") or config.get("competitor_limit") or 10)
    region = filters.get("region") or config.get("region")
    manual_inputs = _manual_competitor_inputs(config, filters)
    manual_mode = bool(manual_inputs)

    if manual_mode:
        candidates, resolve_warnings = await resolve_manual_competitors(
            manual_inputs,
            region=region,
        )
        filters_applied = {
            "region": region,
            "competitors": manual_inputs,
            "competitor_limit": competitor_limit,
            "matching_mode": "manual",
            "discovery_warnings": resolve_warnings,
        }
        if not candidates:
            state["error"] = (
                "No valid competitor Instagram accounts could be resolved from the names provided. "
                "Use @handles or check TRAVILY_API_KEY for company name lookup."
            )
            resetDiscoveryState(state)
            return state
    else:
        try:
            candidates, filters_applied = await discover_competitors(
                company_name=company_name,
                industry=filters.get("industry") or config.get("industry"),
                category=filters.get("category") or config.get("category"),
                region=region,
                country=filters.get("country") or config.get("country"),
                city=filters.get("city") or config.get("city"),
                keywords=filters.get("keywords") or config.get("keywords") or [],
                company_description=company.get("description") or config.get("company_description"),
                company_profile=company.get("profile") or config.get("company_profile"),
                company_signals=company.get("company_signals") or config.get("company_signals"),
                company_username=company.get("instagram_username") or config.get("company_username"),
                company_website=company.get("website") or config.get("company_website"),
                exclude_usernames=filters.get("exclude_usernames") or config.get("exclude_usernames") or [],
                limit=competitor_limit,
            )
        except Exception:
            logger.exception("Failed to discover competitors for company=%s", company_name)
            state["error"] = "Competitor discovery failed due to an internal error. Check server logs."
            resetDiscoveryState(state)
            return state

        if not candidates:
            location = filters_applied.get("city") or filters_applied.get("country") or filters_applied.get("region")
            location_hint = f" in {location}" if location else ""
            state["error"] = (
                f"No competitor Instagram accounts found for {company_name}{location_hint}. "
                "Try widening region, add competitor names, or check TRAVILY_API_KEY."
            )
            resetDiscoveryState(state)
            return state

    if manual_mode:
        candidates = candidates[:competitor_limit]
        candidate_usernames = [item["username"] for item in candidates if item.get("username")]
    else:
        pool_size = min(len(candidates), competitor_limit * CANDIDATE_POOL_MULTIPLIER)
        candidate_usernames = [item["username"] for item in candidates[:pool_size] if item.get("username")]

    candidate_map = {item["username"]: item for item in candidates if item.get("username")}

    post_limit = int(filters.get("post_limit") or config.get("post_limit") or 15)
    delay_seconds = float(
        filters.get("request_delay_seconds") or config.get("request_delay_seconds") or 2.0
    )

    try:
        posts, profiles_by_username = await fetch_instagram_posts_for_usernames(
            candidate_usernames,
            influencer_by_username=candidate_map,
            delay_seconds=delay_seconds,
            post_limit=post_limit,
            return_profiles=True,
        )
    except InstagramRateLimitError:
        state["error"] = "Instagram API rate limit reached. Wait a few minutes and retry."
        state["discovered_posts"] = []
        state["raw_posts"] = []
        return state
    except Exception:
        logger.exception("Failed to fetch competitor posts for usernames=%s", candidate_usernames)
        state["error"] = "Competitor post fetching failed due to an internal error. Check server logs."
        state["discovered_posts"] = []
        state["raw_posts"] = []
        return state

    if not posts:
        if profiles_by_username:
            state["error"] = (
                "Competitor profiles were fetched but no posts were returned. "
                "Try lowering post_limit or retry."
            )
        else:
            state["error"] = (
                "Competitors were found but Instagram API timed out fetching their profiles. "
                "Check network access to graph.facebook.com, verify IG_USER_ID and "
                "INSTAPAGE_ACCESS_TOKEN, then retry."
            )
        state["discovered_posts"] = []
        state["raw_posts"] = []
        return state

    if manual_mode:
        ranked = []
        for candidate in candidates:
            username = candidate.get("username")
            if not username:
                continue
            profile = profiles_by_username.get(username) or {}
            ranked.append(
                {
                    **candidate,
                    "name": profile.get("name") or candidate.get("name"),
                    "bio": profile.get("biography") or candidate.get("bio"),
                    "followers": int(profile.get("followers_count") or candidate.get("followers") or 0),
                    "website": profile.get("website") or candidate.get("website"),
                }
            )
    else:
        intel = filters_applied.get("competitor_intelligence") or {}
        target_keywords = intel.get("target_keywords") or filters.get("keywords") or []

        ranked = rank_competitors(
            candidates,
            profiles_by_username=profiles_by_username,
            target_keywords=target_keywords,
            company_signals=company.get("company_signals") or config.get("company_signals"),
            region=region,
            min_match_score=MIN_MATCH_SCORE,
            limit=competitor_limit,
        )

        min_followers = filters.get("min_followers") or config.get("min_followers")
        if min_followers:
            ranked = [
                item
                for item in ranked
                if int(item.get("followers") or 0) >= int(min_followers)
            ]

        if not ranked:
            state["error"] = (
                "Candidates were found but none passed smart relevance matching. "
                "Try a broader region or verify company profile describes your services clearly."
            )
            resetDiscoveryState(state)
            return state

    ranked_usernames = {item["username"] for item in ranked}
    posts = [post for post in posts if post.get("username") in ranked_usernames]

    media_types = filters.get("media_types") or config.get("media_types") or []
    if media_types:
        allowed = {item.lower() for item in media_types}
        posts = [
            post
            for post in posts
            if (post.get("normalized_media_type") or "").lower() in allowed
        ]

    if not posts:
        state["error"] = (
            "Matched competitors were found but no posts matched your filters. "
            "Try adjusting media_types or post_limit."
        )
        state["discovered_posts"] = []
        state["raw_posts"] = []
        return state

    config["discovery_source"] = "manual_competitors" if manual_mode else "smart_competitor_search"
    config["filters_applied"] = filters_applied
    state["config"] = config
    state["discovered_influencers"] = ranked
    state["discovered_posts"] = posts
    state["raw_posts"] = posts
    return state
