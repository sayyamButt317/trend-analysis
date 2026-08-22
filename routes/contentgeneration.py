from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from agents.contentgeneration.Invoke.generation_invoke import contentGenerationAgent
from agents.contentgeneration.schemas.generation_request import ContentGenerationRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content-generation", tags=["Content Generation"])


@router.post("/video")
async def generate_video(request: ContentGenerationRequest):
    """
    Produce stills and video from a finished script.

    Pass `project`, `script`, `characters`, and `scenes` from POST /script-generation/script.
    """
    try:
        return await contentGenerationAgent(request)
    except Exception as exc:
        logger.exception("Content generation endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
