from fastapi import APIRouter, Query

from agents.competitor.invoke.competitor_invoke import competitorAnalysisAgent
from agents.trend.schemas.competitor_request import CompetitorAnalysisRequest
from service.Competitor.analysis_details import (
    create_competitor_report,
    get_competitor_analytics,
    get_stored_report,
    list_stored_competitors,
    list_stored_content,
    list_stored_hashtags,
    list_stored_reports,
)

router = APIRouter(prefix="/competitor-analysis", tags=["Competitor Analysis"])


@router.post(
    "/analyze",
    summary="Analyze competitors from company details + region",
    description=(
        "Send company details + region. Optionally pass competitor names or @handles "
        "to analyze specific accounts; otherwise uses smart matching to discover competitors. "
        "On Vercel/serverless, defaults to 5 competitors to fit the 300s timeout — "
        "pass `competitor_limit: 3` for faster runs."
    ),
)
async def competitorAnalysis(request: CompetitorAnalysisRequest):
    return await competitorAnalysisAgent(request)


@router.get(
    "/analytics",
    summary="Show competitor analytics dashboard data",
    description=(
        "Returns a consolidated analytics view: overview, competitors, content breakdown, "
        "hashtags, and market insights. Omit analysis_id to use the latest saved run."
    ),
)
async def getAnalytics(
    analysis_id: str | None = Query(
        default=None,
        description="Analysis UUID. If omitted, returns analytics for the most recent run.",
    ),
):
    return await get_competitor_analytics(analysis_id)


@router.get(
    "/competitors",
    summary="List stored competitor profiles from the database",
    description=(
        "Returns competitor profiles saved from past analysis runs. "
        "Pass analysis_id to filter a single run."
    ),
)
async def getStoredCompetitors(
    analysis_id: str | None = Query(default=None, description="Filter by analysis UUID"),
):
    return await list_stored_competitors(analysis_id)


@router.get(
    "/content",
    summary="List stored post content from the database",
    description=(
        "Returns all analyzed posts saved in past runs. "
        "Pass analysis_id to filter a single run."
    ),
)
async def getStoredContent(
    analysis_id: str | None = Query(default=None, description="Filter by analysis UUID"),
):
    return await list_stored_content(analysis_id)


@router.get(
    "/hashtags",
    summary="List stored hashtags from the database",
    description=(
        "Returns aggregated hashtags from saved analyses, with optional per-run breakdown. "
        "Pass analysis_id to filter a single run."
    ),
)
async def getStoredHashtags(
    analysis_id: str | None = Query(default=None, description="Filter by analysis UUID"),
):
    return await list_stored_hashtags(analysis_id)


@router.post(
    "/report",
    summary="Create and store a competitor analysis report",
    description=(
        "Builds a structured report for a saved analysis run and persists it to the reports table."
    ),
)
async def createReport(
    analysis_id: str = Query(..., description="Analysis UUID to generate the report from"),
):
    return await create_competitor_report(analysis_id)


@router.get(
    "/reports",
    summary="List stored reports from the database",
    description="Returns saved report summaries. Pass analysis_id to filter by analysis run.",
)
async def getStoredReports(
    analysis_id: str | None = Query(default=None, description="Filter by analysis UUID"),
):
    return await list_stored_reports(analysis_id)


@router.get(
    "/reports/{report_id}",
    summary="Get a stored report by ID",
    description="Returns the full report JSON saved in the reports table.",
)
async def getStoredReportById(report_id: str):
    return await get_stored_report(report_id)
