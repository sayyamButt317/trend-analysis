from fastapi import APIRouter, Query

from agents.trend.invoke.trend_invoke import globalTrendInvoke
from agents.trend.schemas.trend_request import GlobalTrendRequest
from service.Trend.trend_details import (
    get_stored_trend,
    get_trend_analytics,
    list_stored_trend_hashtags,
    list_stored_trend_scores,
    list_stored_trends,
    list_stored_viral_posts,
)

router = APIRouter(prefix="/trend-analysis", tags=["Global Trend Analysis"])


@router.get(
    "/today",
    summary="Global trends today",
    description=(
        "No input required. Crawls trend websites (SocialBee, Metricool, Sprout Social, "
        "Reddit, X, Facebook, LinkedIn) and Google Trends top/rising queries by country."
    ),
)
async def discoverTrendsToday():
    return await globalTrendInvoke(GlobalTrendRequest())


@router.post(
    "/today",
    summary="Global trends with optional region",
    description="Same as GET /today but accepts an optional region for Google Trends geos.",
)
async def discoverTrendsTodayPost(request: GlobalTrendRequest | None = None):
    return await globalTrendInvoke(request or GlobalTrendRequest())


@router.get(
    "/analytics",
    summary="Show trend analytics dashboard data",
    description=(
        "Returns a consolidated view: overview, trend scores, viral posts, "
        "hashtags, topics, and influencers. Omit trend_id for the latest run."
    ),
)
async def getTrendAnalytics(
    trend_id: str | None = Query(
        default=None,
        description="Trend run UUID. If omitted, returns analytics for the most recent run.",
    ),
):
    return await get_trend_analytics(trend_id)


@router.get(
    "/trends",
    summary="List saved trend discovery runs",
    description="Returns summaries of all trend runs stored in Supabase.",
)
async def getStoredTrends():
    return await list_stored_trends()


@router.get(
    "/trends/{trend_id}",
    summary="Get a saved trend run by ID",
    description="Returns the full trend row including result JSON from Supabase.",
)
async def getStoredTrendById(trend_id: str):
    return await get_stored_trend(trend_id)


@router.get(
    "/hashtags",
    summary="List hashtags from saved trend runs",
    description=(
        "Returns aggregated hashtags from saved trend runs. "
        "Pass trend_id to filter a single run."
    ),
)
async def getStoredTrendHashtags(
    trend_id: str | None = Query(default=None, description="Filter by trend run UUID"),
):
    return await list_stored_trend_hashtags(trend_id)


@router.get(
    "/viral-posts",
    summary="List viral posts from saved trend runs",
    description=(
        "Returns viral posts detected across saved runs. "
        "Pass trend_id to filter a single run."
    ),
)
async def getStoredViralPosts(
    trend_id: str | None = Query(default=None, description="Filter by trend run UUID"),
):
    return await list_stored_viral_posts(trend_id)


@router.get(
    "/trend-scores",
    summary="List trend scores from saved runs",
    description=(
        "Returns scored hashtag/topic/creator trends. "
        "Pass trend_id to filter a single run."
    ),
)
async def getStoredTrendScores(
    trend_id: str | None = Query(default=None, description="Filter by trend run UUID"),
):
    return await list_stored_trend_scores(trend_id)
