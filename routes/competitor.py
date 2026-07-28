from fastapi import APIRouter
from agents.competitor.invoke.competitor_invoke import competitorAnalysisAgent
from agents.trend.schemas.competitor_request import CompetitorAnalysisRequest

router = APIRouter(prefix="/competitor-analysis", tags=["Competitor Analysis"])

@router.post(
    "/analyze",
    summary="Analyze competitors from company details + region",
    description=(
        "Send company details + region. Optionally pass competitor names or @handles "
        "to analyze specific accounts; otherwise uses smart matching to discover competitors."
    ),
)
async def competitorAnalysis(request: CompetitorAnalysisRequest):
    return await competitorAnalysisAgent(request)
