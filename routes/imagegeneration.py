from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException, Query
from agents.imagegeneration.Invoke.image_invoke import imageGenerationAgent
from agents.imagegeneration.schemas.image_request import ImageGenerationRequest
from db.images_storage import (
    delete_image_generation,
    flatten_generated_images,
    get_image_generation,
    list_image_generations,
    list_image_generations_full,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/image-generation", tags=["Image Generation"])


@router.post(
    "/images",
    summary="Generate still images from a script",
    description=(
        "Generate still images from a script-generator result. Pass `platform` + "
        "`purpose` (`story` | `post` | `carousel` | `reel`) plus `project` / `script` / "
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


@router.get(
    "/company/{company_id}/images",
    summary="Get all generated images for a company",
    description=(
        "Returns every saved image-generation run for this `company_id`, plus a "
        "flattened `generated_images` list (S3 URLs) across all runs."
    ),
)
async def getAllCompanyImages(
    company_id: str,
    limit: int = Query(default=50, ge=1, le=100),
):
    company_id = (company_id or "").strip()
    if not company_id:
        raise HTTPException(status_code=400, detail="company_id is required")
    try:
        runs = await list_image_generations_full(company_id=company_id, limit=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    images = flatten_generated_images(runs)
    return {
        "success": True,
        "company_id": company_id,
        "runs_count": len(runs),
        "images_count": len(images),
        "runs": [
            {
                "images_id": row.get("id"),
                "created_at": row.get("created_at"),
                "status": row.get("status"),
                "platform": row.get("platform"),
                "purpose": row.get("purpose"),
                "images_count": row.get("images_count"),
                "generated_images": row.get("generated_images") or [],
            }
            for row in runs
        ],
        "generated_images": images,
    }


@router.delete(
    "/results/{company_id}",
    summary="Delete the latest saved image generation by company_id",
    description=(
        "Deletes the most recent image generation row for the given external "
        "`company_id`, the orphaned prompt row when unused, and related S3 objects "
        "when `s3_key` values are present. Pass `delete_s3=false` to keep S3 files."
    ),
)
async def deleteImageGenerationByCompany(
    company_id: str,
    delete_s3: bool = Query(
        default=True,
        description="Also delete S3 objects referenced by generated_images.s3_key.",
    ),
):
    try:
        return await delete_image_generation(company_id=company_id, delete_s3=delete_s3)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/images/{images_id}",
    summary="Delete a saved image generation by images_id",
    description=(
        "Deletes a specific image generation row by its `images_id` "
        "(from POST /images meta.images_id or GET results). Also removes related "
        "S3 objects unless `delete_s3=false`."
    ),
)
async def deleteImageGenerationById(
    images_id: str,
    delete_s3: bool = Query(
        default=True,
        description="Also delete S3 objects referenced by generated_images.s3_key.",
    ),
):
    try:
        return await delete_image_generation(images_id=images_id, delete_s3=delete_s3)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
