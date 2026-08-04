from fastapi import APIRouter

from agents.nichetrend.invoke.nichetrend_invoke import nicheTrendInvoke
from agents.nichetrend.schemas.nichetrend_request import NicheTrendRequest

router = APIRouter(prefix="/niche-trend", tags=["Niche Trend Analysis"])


@router.post(
    "/discover",
    summary="Niche trend discovery for your company",
    description=(
        "Analyzes your company DNA, Instagram niche, and **audience pain points** "
        "(customer problems — not the company's internal issues), "
        "then discovers niche competitors and merges filtered web trends.\n\n"
        "**Required:** `company_data`, `region`\n"
        "**Recommended:** `instausername`, `linkedinusername`"
    ),
)
async def discoverNicheTrends(request: NicheTrendRequest):
    return await nicheTrendInvoke(request)
