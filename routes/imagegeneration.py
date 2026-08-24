from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from agents.imagegeneration.Invoke.image_invoke import imageGenerationAgent
from agents.imagegeneration.schemas.image_request import ImageGenerationRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/image-generation", tags=["Image Generation"])


@router.post("/images")
async def generate_images(request: ImageGenerationRequest):
    """
    Generate still images from a script-generator result.

    Pass `platform` + `purpose` (`story` | `post` | `carousel`) plus
    `project` / `script` / `scenes` from POST /script-generation/script.
    Uses Gemini (`GEMINI_API_KEY` / `GEMINI_IMAGE_MODEL`).
    """
    try:
        return await imageGenerationAgent(request)
    except Exception as exc:
        logger.exception("Image generation endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
