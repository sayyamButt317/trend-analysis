from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException, Query
from agents.imagegeneration.Invoke.image_invoke import imageGenerationAgent
from agents.imagegeneration.schemas.image_request import ImageGenerationRequest
from db.images_storage import get_image_generation, list_image_generations

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/image-generation", tags=["Image Generation"])


@router.post(
    "/images",
    summary="Generate still images from a script",
    description=(
        "Generate still images from a script-generator result. Pass `platform` + "
        "`purpose` (`story` | `post` | `carousel`) plus `project` / `script` / "
        "`scenes` from POST /script-generation/script. Pass `company_id` to link "
        "the run and retrieve it later via GET /image-generation/results/{company_id}. "
        "Results are stored in SUPABASE_TABLE_IMAGES when Supabase is configured. "
        "Uses Gemini (`GEMINI_API_KEY` / `GEMINI_IMAGE_MODEL`)."
    ),
)
async def generate_images(request: ImageGenerationRequest):
    try:
        return await imageGenerationAgent(request)
    except Exception as exc:
        logger.exception("Image generation endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/results",
    summary="List saved image generation runs",
    description="Returns recent image generation runs. Pass `company_id` to filter.",
)
async def listImageGenerations(
    limit: int = Query(default=20, ge=1, le=100),
    company_id: str | None = Query(
        default=None,
        description="External company_id from POST /images.",
    ),
):
    try:
        rows = await list_image_generations(limit=limit, company_id=company_id)
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
    summary="Get the latest image generation by company_id",
    description=(
        "Returns the most recent image generation result for the given "
        "external `company_id` (the same value passed to POST /images)."
    ),
)
async def getImageGeneration(company_id: str):
    try:
        row = await get_image_generation(company_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Image generation not found for company_id: {company_id}",
        )
    return {
        "success": True,
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
