from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from agents.scriptgenerator.Invoke.script_invoke import scriptGenerationAgent
from agents.scriptgenerator.schemas.script_request import ScriptGenerationRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/script-generation", tags=["Script Generation"])


@router.post("/script")
async def generate_script(request: ScriptGenerationRequest):
    try:
        return await scriptGenerationAgent(request)
    except Exception as exc:
        logger.exception("Script generation endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
