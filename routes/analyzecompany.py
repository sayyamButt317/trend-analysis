from fastapi import APIRouter, HTTPException, Query

from agents.analyzecompany.invoke.company_invoke import analyzeCompanyAgent
from agents.analyzecompany.schemas.company_request import AnalyzeCompanyRequest
from db.company_storage import get_company_analysis, list_company_analyses

router = APIRouter(prefix="/analyze-company", tags=["Analyze Company"])


@router.post(
    "/analyze",
    summary="Analyze your company from website URL (+ optional Instagram/LinkedIn)",
    description=(
        "Primary input is `website_url` — the agent crawls the site, extracts services/"
        "tech/positioning, then optionally enriches with Instagram + LinkedIn. "
        "`company_data` is optional extra text. Pass `company_id` to link the run to your "
        "company record. Result is stored in SUPABASE_TABLE_ANALYSIS "
        "and returned as reusable `company` + `summary_text` + `company_analysis` "
        "for competitor analysis."
    ),
)
async def analyzeCompany(request: AnalyzeCompanyRequest):
    return await analyzeCompanyAgent(request)


@router.get(
    "/results",
    summary="List saved company analyses",
    description=(
        "Returns recent analyze-company runs. Pass `company_id` to filter to one company."
    ),
)
async def listCompanyAnalyses(
    limit: int = Query(default=20, ge=1, le=100),
    company_id: str | None = Query(
        default=None,
        description="External company_id from POST /analyze — filters results for that company.",
    ),
):
    try:
        rows = await list_company_analyses(limit=limit, company_id=company_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "success": True,
        "count": len(rows),
        "company_id": company_id,
        "results": rows,
    }


@router.get(
    "/results/{company_id}",
    summary="Get the latest saved company analysis by company_id",
    description=(
        "Looks up the most recent analyze-company result for the given external "
        "`company_id` (the same value passed to POST /analyze)."
    ),
)
async def getCompanyAnalysis(company_id: str):
    try:
        row = await get_company_analysis(company_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Company analysis not found for company_id: {company_id}",
        )
    return {
        "success": True,
        "analysis_id": row.get("id"),
        "prompt_id": row.get("prompt_id"),
        "company_id": row.get("company_id") or company_id,
        "created_at": row.get("created_at"),
        "status": row.get("status"),
        "summary": row.get("summary"),
        "result": row.get("result"),
    }
