from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from agents.outreach.invoke.outreach_invoke import linkedinOutreachAgent
from agents.outreach.schemas.outreach_request import LinkedInOutreachRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/outreach", tags=["Outreach"])


@router.post("/linkedin")
async def linkedin_outreach(request: LinkedInOutreachRequest):
    """
    Open a LinkedIn profile with Playwright (using LINKEDIN_EMAIL/PASSWORD or LINKEDIN_LI_AT),
    send a connection request (optional note), and send a message when already connected.
    """
    try:
        return await linkedinOutreachAgent(request)
    except Exception as exc:
        logger.exception("Outreach endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
