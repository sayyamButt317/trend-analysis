from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException
from agents.contentrecommendation.invoke.contentinvoke import contentRecommendationAgent
from agents.contentrecommendation.schemas.content_request import ContentRecommendationRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content-recommendation", tags=["Content Recommendation"])


@router.post("/recommend")
async def recommend_content(request: ContentRecommendationRequest):
    try:
        return await contentRecommendationAgent(request)
    except Exception as exc:
        logger.exception("Content recommendation endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
