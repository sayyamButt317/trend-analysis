import logging
from typing import Any
from agents.competitor.pipeline_log import log_event
from agents.competitor.state.competitor_state import CompetitorState
from agents.trend.services.company_social_analyzer import resolve_company_social_handles
from agents.trend.services.instagramuser_details import InstagramRateLimitError
from service.AnalyzeUserInstagram.contentstrategy import build_instagram_analysis
from service.AnalyzeUserInstagram.fetchprofile import (

    fetch_user_instagram_profile,

    posts_from_profile,

)



logger = logging.getLogger(__name__)



Competitor = dict[str, Any]





async def analyze_competitor_instagram(

    competitor: Competitor,

    *,

    region: str | None = None,

    post_limit: int = 15,

) -> Competitor:

    """Fetch and analyze a competitor's Instagram presence."""

    username = (competitor.get("username") or "").strip().lstrip("@").lower()

    name = (competitor.get("name") or username or "").strip()

    warnings: list[str] = list(competitor.get("social_warnings") or [])



    if not username and name:

        handles = await resolve_company_social_handles(

            {

                "name": name,

                "website": competitor.get("website"),

                "profile": competitor.get("bio") or "",

            },

            region=region,

            resolve_linkedin=False,

        )

        username = (handles.get("instagram_username") or "").strip().lstrip("@").lower()

        if handles.get("instagram_url"):

            competitor["profile_url"] = handles["instagram_url"]



    enriched = dict(competitor)

    if not username:

        warnings.append(f"No Instagram account found for competitor '{name}'.")

        enriched["social_warnings"] = warnings

        enriched["instagram_analysis"] = None

        return enriched



    profile = competitor.get("instagram_profile")

    posts = list(competitor.get("instagram_posts") or [])



    if not profile:

        try:

            profile = await fetch_user_instagram_profile(username, post_limit=post_limit)

        except InstagramRateLimitError:

            raise

        except Exception:

            logger.warning("Instagram analysis failed for @%s", username, exc_info=True)

            profile = None



    if profile and not posts:

        posts = posts_from_profile(profile, handle=username)



    if not profile:

        warnings.append(f"Could not fetch Instagram profile for @{username}.")

        enriched.update(

            {

                "username": username,

                "profile_url": enriched.get("profile_url") or f"https://www.instagram.com/{username}/",

                "social_warnings": warnings,

                "instagram_analysis": None,

            }

        )

        return enriched



    if not posts:

        posts = posts_from_profile(profile, handle=username)

    analysis = build_instagram_analysis(profile, posts)



    enriched.update(

        {

            "username": profile.get("username") or username,

            "name": profile.get("name") or name,

            "bio": profile.get("biography") or profile.get("bio") or competitor.get("bio"),

            "followers": int(profile.get("followers_count") or competitor.get("followers") or 0),

            "website": profile.get("website") or competitor.get("website"),

            "profile_picture_url": profile.get("profile_picture_url"),

            "profile_url": enriched.get("profile_url") or f"https://www.instagram.com/{username}/",

            "instagram_profile": profile,

            "instagram_posts": posts,

            "instagram_analysis": analysis,

            "social_warnings": warnings,

        }

    )

    return enriched





async def analyzeCompetitorInsta(competitor: Competitor) -> Competitor:

    return await analyze_competitor_instagram(competitor)





async def AnalyzeCompetitorInstaNode(state: CompetitorState) -> CompetitorState:

    if state.get("error"):

        return state



    config = state.get("config") or {}

    filters = config.get("filters") or config

    region = filters.get("region") or config.get("region")

    post_limit = int(filters.get("post_limit") or config.get("post_limit") or 15)



    competitors = state.get("discovered_influencers") or state.get("competitors") or []

    enriched: list[Competitor] = []

    log_event(
        "3_competitor_social",
        "Analyzing competitor Instagram profiles",
        competitors=len(competitors),
        post_limit=post_limit,
    )



    for competitor in competitors:

        username = competitor.get("username") or competitor.get("name")
        log_event("3_competitor_social", "Competitor Instagram", username=f"@{username}" if username else "unknown")

        try:

            item = await analyze_competitor_instagram(

                competitor,

                region=region,

                post_limit=post_limit,

            )

            enriched.append(item)

        except InstagramRateLimitError:

            state["error"] = "Instagram API rate limit reached. Wait a few minutes and retry."

            return state

        except Exception:

            logger.exception(

                "Instagram analysis failed for competitor=%s",

                competitor.get("username") or competitor.get("name"),

            )

            enriched.append({**competitor, "instagram_analysis": None})



    state["discovered_influencers"] = enriched

    state["competitors"] = enriched

    analyzed = sum(1 for item in enriched if item.get("instagram_analysis"))
    log_event(
        "3_competitor_social",
        "Competitor Instagram analysis finished",
        analyzed=analyzed,
        total=len(enriched),
    )

    return state


