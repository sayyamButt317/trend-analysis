from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException, Query
from db.content_recommendation_storage import list_content_recommendations_full
from db.images_storage import flatten_generated_images, list_image_generations_full
from db.script_storage import list_script_generations_full
from service.ContentRecommendation.builder import sanitize_content_recommendation_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/company-content", tags=["Company Content"])


@router.get(
    "/{company_id}",
    summary="Get all generated content for a company",
    description=(
        "Returns all saved content recommendations, scripts, and generated images "
        "for the given external `company_id`. Also includes a flattened "
        "`generated_images` list across all image runs."
    ),
)
async def getCompanyGeneratedContent(
    company_id: str,
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
        description="Max runs to return per content type (newest first).",
    ),
):
    company_id = (company_id or "").strip()
    if not company_id:
        raise HTTPException(status_code=400, detail="company_id is required")

    try:
        recommendations = await list_content_recommendations_full(
            company_id=company_id,
            limit=limit,
        )
        scripts = await list_script_generations_full(
            company_id=company_id,
            limit=limit,
        )
        image_runs = await list_image_generations_full(
            company_id=company_id,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    cleaned_recommendations = []
    for row in recommendations:
        public = sanitize_content_recommendation_response(
            {
                "content_strategy": {},
                "platform_strategy": {},
                "content_ideas": row.get("content_ideas") or [],
                "content_calendar": row.get("content_calendar") or {},
                "recommendation": row.get("recommendation") or {},
            }
        )
        cleaned_recommendations.append(
            {
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
                "content_calendar": public.get("content_calendar")
                or row.get("content_calendar")
                or {},
                "content_ideas": public.get("content_ideas") or row.get("content_ideas") or [],
                "recommendation": public.get("recommendation") or {},
            }
        )

    scripts_out = [
        {
            "script_id": row.get("id"),
            "prompt_id": row.get("prompt_id"),
            "company_id": row.get("company_id") or company_id,
            "created_at": row.get("created_at"),
            "status": row.get("status"),
            "summary": row.get("summary"),
            "content_type": row.get("content_type"),
            "platform": row.get("platform"),
            "aspect_ratio": row.get("aspect_ratio"),
            "style": row.get("style"),
            "duration_seconds": row.get("duration_seconds"),
            "scenes_count": row.get("scenes_count"),
            "characters_count": row.get("characters_count"),
            "project": row.get("project") or {},
            "script": row.get("script") or {},
            "characters": row.get("characters") or [],
            "scenes": row.get("scenes") or [],
            "content_suggestion": row.get("content_suggestion") or {},
        }
        for row in scripts
    ]

    image_runs_out = [
        {
            "images_id": row.get("id"),
            "prompt_id": row.get("prompt_id"),
            "company_id": row.get("company_id") or company_id,
            "created_at": row.get("created_at"),
            "status": row.get("status"),
            "summary": row.get("summary"),
            "platform": row.get("platform"),
            "purpose": row.get("purpose"),
            "aspect_ratio": row.get("aspect_ratio"),
            "style": row.get("style"),
            "images_count": row.get("images_count"),
            "jobs_count": row.get("jobs_count"),
            "project": row.get("project") or {},
            "script": row.get("script") or {},
            "image_jobs": row.get("image_jobs") or [],
            "generated_images": row.get("generated_images") or [],
        }
        for row in image_runs
    ]

    all_images = flatten_generated_images(image_runs)

    return {
        "success": True,
        "company_id": company_id,
        "counts": {
            "content_recommendations": len(cleaned_recommendations),
            "scripts": len(scripts_out),
            "image_runs": len(image_runs_out),
            "generated_images": len(all_images),
        },
        "content_recommendations": cleaned_recommendations,
        "scripts": scripts_out,
        "image_runs": image_runs_out,
        "generated_images": all_images,
    }
