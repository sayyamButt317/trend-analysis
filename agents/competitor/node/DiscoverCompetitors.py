import logging
from agents.competitor.pipeline_log import log_event
from agents.competitor.state.competitor_state import CompetitorState
from agents.trend.services.competitor_matcher import (
    DEFAULT_COMPETITOR_TARGET,
    MIN_AUTHENTIC_MATCH_SCORE,
    filter_authentic_competitors,
)
from agents.trend.services.instagram_discovery import fetch_instagram_posts_for_usernames
from agents.trend.services.instagramuser_details import InstagramRateLimitError

logger = logging.getLogger(__name__)


def resetDiscoveryState(state: CompetitorState) -> None:
    state["discovered_influencers"] = []
    state["discovered_posts"] = []
    state["raw_posts"] = []


def _collect_prefetched_posts(competitors: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    posts: list[dict] = []
    profiles_by_username: dict[str, dict] = {}
    for competitor in competitors:
        username = (competitor.get("username") or "").strip().lstrip("@").lower()
        if not username:
            continue
        profile = competitor.get("instagram_profile")
        if profile:
            profiles_by_username[username] = profile
        competitor_posts = competitor.get("instagram_posts") or []
        if competitor_posts:
            posts.extend(competitor_posts)
    return posts, profiles_by_username


async def DiscoverCompetitorsNode(state: CompetitorState) -> CompetitorState:
    if state.get("error"):
        resetDiscoveryState(state)
        return state


    config = state.get("config") or {}
    company = config.get("company") or {}
    filters = config.get("filters") or config
    filters_applied = config.get("filters_applied") or {}

    competitors = state.get("discovered_influencers") or state.get("competitors") or []
    if not competitors:
        state["error"] = "No competitors found. Run competitor discovery first."
        resetDiscoveryState(state)
        return state

    matching_mode = (
        ((config.get("filters_applied") or {}).get("matching_mode") or "")
        or ((filters_applied.get("matching_mode") or ""))
    ).strip().lower()
    manual_mode = matching_mode in {"manual", "openai_proposal"}

    normalized: list[dict] = []
    for item in competitors:
        socials = dict(item.get("socials") or {})
        username = (item.get("username") or socials.get("instagram") or "").strip().lstrip("@").lower()
        linkedin = item.get("linkedin_url") or socials.get("linkedin")
        if username:
            socials["instagram"] = username
        if linkedin:
            socials["linkedin"] = linkedin
        # Keep peers that have Instagram and/or LinkedIn/website (OpenAI may omit IG).
        if username or linkedin or item.get("website") or manual_mode:
            normalized.append(
                {
                    **item,
                    "username": username or None,
                    "linkedin_url": linkedin,
                    "socials": socials,
                }
            )
    competitors = normalized
    if not competitors:
        state["error"] = "Competitors were found but none had resolvable Instagram or LinkedIn profiles."
        resetDiscoveryState(state)
        return state

    competitor_limit = int(
        filters.get("competitor_limit")
        or config.get("competitor_target")
        or config.get("competitor_limit")
        or DEFAULT_COMPETITOR_TARGET
    )
    region = filters.get("region") or config.get("region")

    with_instagram = [item for item in competitors if item.get("username")]
    if not with_instagram and not manual_mode:
        state["error"] = "Competitors were found but none had resolvable Instagram handles."
        resetDiscoveryState(state)
        return state
    if not with_instagram and manual_mode:
        log_event(
            "2_discovery",
            "No Instagram handles on proposed competitors — continuing with LinkedIn/website only",
            competitors=len(competitors),
        )
        ranked = [
            {
                **item,
                "region_match": True,
                "niche_match": True,
                "authenticity": matching_mode or "openai_proposal",
            }
            for item in competitors[:competitor_limit]
        ]
        state["discovered_influencers"] = ranked
        state["competitors"] = ranked
        state["discovered_posts"] = []
        state["raw_posts"] = []
        state["config"] = config
        return state

    candidate_usernames = [
        (item.get("username") or "").strip().lstrip("@").lower()
        for item in with_instagram
        if item.get("username")
    ]

    post_limit = int(filters.get("post_limit") or config.get("post_limit") or 10)
    delay_seconds = float(
        filters.get("request_delay_seconds") or config.get("request_delay_seconds") or 1.5
    )

    posts, profiles_by_username = _collect_prefetched_posts(with_instagram)
    missing_usernames = [
        handle for handle in candidate_usernames if handle and handle not in profiles_by_username
    ]
    log_event(
        "2_discovery",
        "Fetching competitor Instagram posts",
        competitors=len(competitors),
        with_instagram=len(with_instagram),
        post_limit=post_limit,
        to_fetch=len(missing_usernames),
        prefetched=len(profiles_by_username),
    )

    if missing_usernames:
        candidate_map = {
            (item.get("username") or "").strip().lstrip("@").lower(): item
            for item in with_instagram
            if item.get("username")
        }
        try:
            fetched_posts, fetched_profiles = await fetch_instagram_posts_for_usernames(
                missing_usernames,
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
            logger.exception("Failed to fetch competitor posts for usernames=%s", missing_usernames)
            state["error"] = "Competitor post fetching failed due to an internal error. Check server logs."
            state["discovered_posts"] = []
            state["raw_posts"] = []
            return state

        posts.extend(fetched_posts)
        profiles_by_username.update(fetched_profiles)

    if not profiles_by_username:
        if manual_mode:
            log_event(
                "2_discovery",
                "Instagram profiles unavailable — keeping OpenAI/manual competitors",
                competitors=len(competitors),
            )
            ranked = [
                {
                    **item,
                    "region_match": True,
                    "niche_match": True,
                    "authenticity": matching_mode or "openai_proposal",
                }
                for item in competitors[:competitor_limit]
            ]
            state["discovered_influencers"] = ranked
            state["competitors"] = ranked
            state["discovered_posts"] = []
            state["raw_posts"] = []
            state["config"] = config
            return state
        state["error"] = (
            "Competitors were found but Instagram API timed out fetching their profiles. "
            "Check IG_USER_ID and INSTAPAGE_ACCESS_TOKEN, then retry."
        )
        state["discovered_posts"] = []
        state["raw_posts"] = []
        return state

    if manual_mode:
        ranked = []
        for candidate in competitors[:competitor_limit]:
            username = (candidate.get("username") or "").strip().lstrip("@").lower()
            profile = profiles_by_username.get(username) or {} if username else {}
            ranked.append(
                {
                    **candidate,
                    "name": profile.get("name") or candidate.get("name"),
                    "bio": profile.get("biography") or profile.get("bio") or candidate.get("bio"),
                    "followers": int(
                        profile.get("followers_count") or candidate.get("followers") or 0
                    ),
                    "website": profile.get("website") or candidate.get("website"),
                    "profile_picture_url": profile.get("profile_picture_url")
                    or candidate.get("profile_picture_url"),
                    "instagram_profile": profile or None,
                    "region_match": True,
                    "niche_match": True,
                    "authenticity": matching_mode or "openai_proposal",
                }
            )
    else:
        intel = filters_applied.get("competitor_intelligence") or {}
        target_keywords = intel.get("target_keywords") or filters.get("keywords") or []

        ranked = filter_authentic_competitors(
            with_instagram,
            profiles_by_username=profiles_by_username,
            target_keywords=target_keywords,
            company_signals=company.get("company_signals") or config.get("company_signals"),
            region=region,
            limit=competitor_limit,
            min_match_score=MIN_AUTHENTIC_MATCH_SCORE,
            require_region=True,
            require_niche=True,
        )

        if len(ranked) < competitor_limit:
            filters_applied["discovery_warnings"] = [
                *list(filters_applied.get("discovery_warnings") or []),
                (
                    f"Only {len(ranked)} authentic competitors matched region '{region}' and company niche "
                    f"out of {len(profiles_by_username)} profiles checked (target was {competitor_limit})."
                ),
            ]
            config["filters_applied"] = filters_applied

        if not ranked:
            ranked = filter_authentic_competitors(
                with_instagram,
                profiles_by_username=profiles_by_username,
                target_keywords=target_keywords,
                company_signals=company.get("company_signals") or config.get("company_signals"),
                region=region,
                limit=competitor_limit,
                min_match_score=max(MIN_AUTHENTIC_MATCH_SCORE - 0.08, 0.2),
                require_region=False,
                require_niche=True,
            )
            if ranked:
                filters_applied["discovery_warnings"] = [
                    *list(filters_applied.get("discovery_warnings") or []),
                    (
                        f"No strict region matches for '{region}'; kept {len(ranked)} niche-matched "
                        "competitor(s) without requiring region in profile text."
                    ),
                ]
                config["filters_applied"] = filters_applied

        if not ranked:
            state["error"] = (
                f"No authentic competitors matched your company niche in region '{region}'. "
                "Verify company details describe services clearly, or try a broader region."
            )
            resetDiscoveryState(state)
            return state

    ranked_usernames = {
        (item.get("username") or "").strip().lstrip("@").lower()
        for item in ranked
        if item.get("username")
    }

    for item in ranked:
        username = (item.get("username") or "").strip().lstrip("@").lower()
        profile = profiles_by_username.get(username) if username else None
        if profile:
            item["instagram_profile"] = profile
    posts = [post for post in posts if (post.get("username") or "").lower() in ranked_usernames]
    media_types = filters.get("media_types") or config.get("media_types") or []
    if media_types:
        allowed = {item.lower() for item in media_types}
        posts = [
            post
            for post in posts
            if (post.get("normalized_media_type") or "").lower() in allowed
        ]

    if not posts and not manual_mode:
        state["error"] = (
            "Authentic competitors were matched but no posts were returned. "
            "Try lowering post_limit or retry."
        )
        state["discovered_posts"] = []
        state["raw_posts"] = []
        state["discovered_influencers"] = ranked
        state["competitors"] = ranked
        return state

    state["discovered_influencers"] = ranked
    state["competitors"] = ranked
    state["discovered_posts"] = posts
    state["raw_posts"] = posts
    state["config"] = config
    log_event(
        "2_discovery",
        "Competitor Instagram posts ranked & ready",
        ranked=len(ranked),
        posts=len(posts),
        region=region,
        mode=matching_mode or "smart",
    )
    return state
