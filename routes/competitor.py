from fastapi import APIRouter, HTTPException, Query, status

from agents.competitor.invoke.competitor_invoke import competitorAnalysisAgent
from agents.competitor.jobs import create_competitor_job, get_competitor_job
from agents.trend.schemas.competitor_request import CompetitorAnalysisRequest
from service.Competitor.analysis_details import (
    create_competitor_report,
    delete_stored_analysis_result,
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
    summary="Analyze competitors (sync — may 504 behind proxies)",
    description=(
        "Runs the competitor agent. Prefer passing `company`, `summary_text`, and "
        "`company_analysis` from POST /analyze-company/analyze so your website/"
        "Instagram/LinkedIn are not re-analyzed every run. Pass `company_id` to link "
        "and retrieve results later. Long runs often hit gateway 504 — prefer async."
    ),
)
async def competitorAnalysis(request: CompetitorAnalysisRequest):
    return await competitorAnalysisAgent(request)


@router.post(
    "/analyze/async",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start competitor analysis in the background (recommended for frontend)",
    description=(
        "Starts the full competitor agent without waiting. Returns a job_id immediately "
        "so proxies do not 504. Poll GET /competitor-analysis/jobs/{job_id} until "
        "status is completed, then use the embedded result (same shape as sync analyze)."
    ),
)
async def competitorAnalysisAsync(request: CompetitorAnalysisRequest):
    return await create_competitor_job(request)


@router.get(
    "/jobs/{job_id}",
    summary="Poll async competitor analysis job status",
    description=(
        "Returns job status: queued | running | completed | failed. "
        "When completed, includes the full agent result JSON and company_id."
    ),
)
async def getCompetitorJobStatus(job_id: str):
    job = await get_competitor_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    company_id = job.get("company_id")
    payload = {
        "success": True,
        "job_id": job["job_id"],
        "status": job["status"],
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "company_name": job.get("company_name"),
        "company_id": company_id,
        "region": job.get("region"),
        "competitor_limit": job.get("competitor_limit"),
        "elapsed_sec": job.get("elapsed_sec"),
        "prompt_id": job.get("prompt_id"),
        "error": job.get("error"),
        "poll_url": f"/competitor-analysis/jobs/{job_id}",
    }
    if job.get("status") == "completed" and job.get("result") is not None:
        payload["result"] = job["result"]
        if company_id:
            payload["result_url"] = f"/competitor-analysis/results/{company_id}"
    return payload


@router.get(
    "/results/all",
    summary="List all full saved competitor-agent responses",
    description=(
        "Returns every stored competitor analysis payload (same JSON shape as POST /analyze). "
        "Use limit/offset for pagination. Pass company_id to filter one company."
    ),
)
async def listStoredAnalysisResults(
    limit: int = Query(default=20, ge=1, le=100, description="Max runs to return"),
    offset: int = Query(default=0, ge=0, description="Number of runs to skip"),
    company_id: str | None = Query(default=None, description="Filter by external company_id"),
):
    return await list_stored_analysis_results(limit=limit, offset=offset, company_id=company_id)


@router.get(
    "/results",
    summary="Get the latest saved competitor-agent response",
    description=(
        "Returns the exact JSON payload saved from POST /analyze. "
        "Pass company_id for a specific company; omit it to get the most recent run."
    ),
)
async def getStoredAnalysisResult(
    company_id: str | None = Query(
        default=None,
        description="External company_id from POST /analyze. If omitted, returns the most recent run.",
    ),
):
    return await get_stored_analysis_result(company_id)


@router.get(
    "/results/{company_id}",
    summary="Get the latest saved competitor analysis by company_id",
    description=(
        "Returns the most recent competitor analysis result for the given external company_id."
    ),
)
async def getStoredAnalysisResultById(company_id: str):
    return await get_stored_analysis_result(company_id)


@router.delete(
    "/results/{company_id}",
    summary="Delete a saved competitor analysis by company_id",
    description=(
        "Deletes the latest stored analysis row for this company_id, plus related reports "
        "and the orphaned prompt row when nothing else references it."
    ),
)
async def deleteStoredAnalysisResult(company_id: str):
    return await delete_stored_analysis_result(company_id)


@router.get(
    "/analytics",
    summary="Show competitor analytics dashboard data",
    description=(
        "Returns a consolidated analytics view: overview, competitors, content breakdown, "
        "hashtags, and market insights. Pass company_id or omit for the latest run."
    ),
)
async def getAnalytics(
    company_id: str | None = Query(
        default=None,
        description="External company_id. If omitted, returns analytics for the most recent run.",
    ),
):
    return await get_competitor_analytics(company_id)


@router.get(
    "/competitors",
    summary="List stored competitor profiles from the database",
    description=(
        "Returns competitor profiles saved from past analysis runs. "
        "Pass company_id to filter a single company."
    ),
)
async def getStoredCompetitors(
    company_id: str | None = Query(default=None, description="Filter by external company_id"),
):
    return await list_stored_competitors(company_id)


@router.get(
    "/content",
    summary="List stored post content from the database",
    description=(
        "Returns all analyzed posts saved in past runs. "
        "Pass company_id to filter a single company."
    ),
)
async def getStoredContent(
    company_id: str | None = Query(default=None, description="Filter by external company_id"),
):
    return await list_stored_content(company_id)


@router.get(
    "/hashtags",
    summary="List stored hashtags from the database",
    description=(
        "Returns aggregated hashtags from saved analyses, with optional per-run breakdown. "
        "Pass company_id to filter a single company."
    ),
)
async def getStoredHashtags(
    company_id: str | None = Query(default=None, description="Filter by external company_id"),
):
    return await list_stored_hashtags(company_id)


@router.post(
    "/report",
    summary="Create and store a competitor analysis report",
    description=(
        "Builds a structured report for the latest saved analysis of a company_id "
        "and persists it to the reports table."
    ),
)
async def createReport(
    company_id: str = Query(..., description="External company_id to generate the report from"),
):
    return await create_competitor_report(company_id)


@router.get(
    "/reports",
    summary="List stored reports from the database",
    description="Returns saved report summaries. Pass company_id to filter by company.",
)
async def getStoredReports(
    company_id: str | None = Query(default=None, description="Filter by external company_id"),
):
    return await list_stored_reports(company_id)


@router.get(
    "/reports/{company_id}",
    summary="Get the latest stored report by company_id",
    description="Returns the most recent report JSON for this company_id.",
)
async def getStoredReportById(company_id: str):
    return await get_stored_report(company_id)
