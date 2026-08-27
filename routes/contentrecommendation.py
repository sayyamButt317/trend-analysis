from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException, Query
from agents.contentrecommendation.invoke.contentinvoke import contentRecommendationAgent
from agents.contentrecommendation.schemas.content_request import ContentRecommendationRequest
from db.content_recommendation_storage import (
    delete_content_recommendation,
    get_content_recommendation,
    list_content_recommendations,
)
from service.ContentRecommendation.builder import sanitize_content_recommendation_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/content-recommendation", tags=["Content Recommendation"])


@router.post(
    "/recommend",
    summary="Generate content recommendations",
    description=(
        "Builds content strategy, ideas, and a production-ready calendar. "
        "Pass `company_id` to link the run and retrieve it later via "
        "GET /content-recommendation/results/{company_id}. "
        "Results are stored in SUPABASE_TABLE_CONTENT_RECOMMENDATION when Supabase is configured."
    ),
)
async def recommend_content(request: ContentRecommendationRequest):
    try:
        return await contentRecommendationAgent(request)
    except Exception as exc:
        logger.exception("Content recommendation endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/results",
    summary="List saved content recommendation runs",
    description="Returns recent content recommendation runs. Pass `company_id` to filter.",
)
async def listContentRecommendations(
    limit: int = Query(default=20, ge=1, le=100),
    company_id: str | None = Query(
        default=None,
        description="External company_id from POST /recommend.",
    ),
):
    try:
        rows = await list_content_recommendations(limit=limit, company_id=company_id)
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
    summary="Get the latest content recommendation by company_id",
    description=(
        "Returns the most recent content recommendation result for the given "
        "external `company_id` (the same value passed to POST /recommend)."
    ),
)
async def getContentRecommendation(company_id: str):
    try:
        row = await get_content_recommendation(company_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Content recommendation not found for company_id: {company_id}",
        )
    stored_result = row.get("result") if isinstance(row.get("result"), dict) else {}
    public = sanitize_content_recommendation_response(stored_result) if stored_result else {}
    recommendation = sanitize_content_recommendation_response(
        {"recommendation": row.get("recommendation") or public.get("recommendation") or {}}
    ).get("recommendation") or {}
    return {
        "success": True,
        "content_recommendation_id": row.get("id"),
        "prompt_id": row.get("prompt_id"),
        "company_id": row.get("company_id") or company_id,
        "company_name": row.get("company_name"),
        "created_at": row.get("created_at"),
        "status": row.get("status"),
        "summary": row.get("summary"),
        "platforms": row.get("platforms") or [],
        "ideas_count": row.get("ideas_count"),
        "calendar_items_count": row.get("calendar_items_count"),
        "content_strategy": public.get("content_strategy") or {},
        "platform_strategy": public.get("platform_strategy") or {},
        "content_calendar": row.get("content_calendar") or public.get("content_calendar") or {},
        "content_ideas": row.get("content_ideas") or public.get("content_ideas") or [],
        "recommendation": recommendation,
    }


@router.delete(
    "/results/{company_id}",
    summary="Delete the latest saved content recommendation by company_id",
    description=(
        "Deletes the most recent content recommendation row for the given external "
        "`company_id`, and the orphaned prompt row when nothing else references it."
    ),
)
async def deleteContentRecommendationByCompany(company_id: str):
    try:
        return await delete_content_recommendation(company_id=company_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/recommend/{content_recommendation_id}",
    summary="Delete a saved content recommendation by id",
    description=(
        "Deletes a specific content recommendation row by its "
        "`content_recommendation_id` (from POST /recommend meta or GET results)."
    ),
)
async def deleteContentRecommendationById(content_recommendation_id: str):
    try:
        return await delete_content_recommendation(
            content_recommendation_id=content_recommendation_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
