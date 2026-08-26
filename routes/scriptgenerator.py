from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException, Query

from agents.scriptgenerator.Invoke.script_invoke import scriptGenerationAgent
from agents.scriptgenerator.schemas.script_request import ScriptGenerationRequest
from db.script_storage import (
    delete_script_generation,
    get_script_generation,
    list_script_generations,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/script-generation", tags=["Script Generation"])


@router.post(
    "/script",
    summary="Generate a script from a brief or calendar item",
    description=(
        "Creates an image or video production script. Pass `company_id` to link the run "
        "and retrieve it later via GET /script-generation/results/{company_id}. "
        "Results are stored in SUPABASE_TABLE_SCRIPT when Supabase is configured."
    ),
)
async def generate_script(request: ScriptGenerationRequest):
    try:
        return await scriptGenerationAgent(request)
    except Exception as exc:
        logger.exception("Script generation endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/results",
    summary="List saved script generation runs",
    description="Returns recent script runs. Pass `company_id` to filter.",
)
async def listScriptGenerations(
    limit: int = Query(default=20, ge=1, le=100),
    company_id: str | None = Query(
        default=None,
        description="External company_id from POST /script.",
    ),
):
    try:
        rows = await list_script_generations(limit=limit, company_id=company_id)
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
    summary="Get the latest script generation by company_id",
    description=(
        "Returns the most recent script generation result for the given "
        "external `company_id` (the same value passed to POST /script)."
    ),
)
async def getScriptGeneration(company_id: str):
    try:
        row = await get_script_generation(company_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Script generation not found for company_id: {company_id}",
        )
    return {
        "success": True,
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


@router.delete(
    "/results/{company_id}",
    summary="Delete the latest saved script by company_id",
    description=(
        "Deletes the most recent script generation row for the given external "
        "`company_id`, and the orphaned prompt row when nothing else references it."
    ),
)
async def deleteScriptGenerationByCompany(company_id: str):
    try:
        return await delete_script_generation(company_id=company_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/script/{script_id}",
    summary="Delete a saved script by script_id",
    description=(
        "Deletes a specific script generation row by its `script_id` "
        "(returned in POST /script meta.script_id or GET /results/{company_id})."
    ),
)
async def deleteScriptGenerationById(script_id: str):
    try:
        return await delete_script_generation(script_id=script_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
