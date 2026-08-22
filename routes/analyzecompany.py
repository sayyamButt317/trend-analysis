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
)
async def listCompanyAnalyses(limit: int = Query(default=20, ge=1, le=100)):
    try:
        rows = await list_company_analyses(limit=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"success": True, "count": len(rows), "results": rows}


@router.get(
    "/results/{analysis_id}",
    summary="Get a saved company analysis by id",
)
async def getCompanyAnalysis(analysis_id: str):
    try:
        row = await get_company_analysis(analysis_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail=f"Company analysis not found: {analysis_id}")
    return {
        "success": True,
        "analysis_id": row.get("id"),
        "prompt_id": row.get("prompt_id"),
        "company_id": row.get("company_id"),
        "created_at": row.get("created_at"),
        "status": row.get("status"),
        "summary": row.get("summary"),
        "result": row.get("result"),
    }
