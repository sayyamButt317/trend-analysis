from fastapi import APIRouter, Query

from agents.competitor.invoke.competitor_invoke import competitorAnalysisAgent
from agents.trend.schemas.competitor_request import CompetitorAnalysisRequest
from service.Competitor.analysis_details import (
    create_competitor_report,
    get_competitor_analytics,
    get_stored_analysis_result,
    get_stored_report,
    list_stored_analysis_results,
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
        "Send company details + region. Optionally pass `company_name`, `instagram_username`, "
        "and/or `linkedin_url`. LinkedIn posts are fetched from "
        "`/company/{slug}/posts/?feedView=all` built from your company name. "
        "You may also pass competitor names or @handles to skip auto-discovery."
    ),
)
async def competitorAnalysis(request: CompetitorAnalysisRequest):
    return await competitorAnalysisAgent(request)


@router.get(
    "/results/all",
    summary="List all full saved competitor-agent responses",
    description=(
        "Returns every stored competitor analysis payload (same JSON shape as POST /analyze). "
        "Use limit/offset for pagination."
    ),
)
async def listStoredAnalysisResults(
    limit: int = Query(default=20, ge=1, le=100, description="Max runs to return"),
    offset: int = Query(default=0, ge=0, description="Number of runs to skip"),
):
    return await list_stored_analysis_results(limit=limit, offset=offset)


@router.get(
    "/results",
    summary="Get the full saved competitor-agent response",
    description=(
        "Returns the exact JSON payload saved from POST /analyze (same shape as the live agent response). "
        "Pass analysis_id for a specific run; omit it to get the latest."
    ),
)
async def getStoredAnalysisResult(
    analysis_id: str | None = Query(
        default=None,
        description="Analysis UUID from meta.analysis_id. If omitted, returns the most recent run.",
    ),
):
    return await get_stored_analysis_result(analysis_id)


@router.get(
    "/results/{analysis_id}",
    summary="Get a full saved competitor-agent response by ID",
    description="Returns the exact JSON payload saved from POST /analyze for this analysis_id.",
)
async def getStoredAnalysisResultById(analysis_id: str):
    return await get_stored_analysis_result(analysis_id)


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
