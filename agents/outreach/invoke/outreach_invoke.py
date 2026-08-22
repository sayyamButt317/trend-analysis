from __future__ import annotations
import time
from datetime import datetime, timezone
from typing import Any
from agents.outreach.graph.outreach_graph import outreach_graph_app
from agents.outreach.pipeline_log import log_event, log_pipeline_complete, log_pipeline_start
from agents.outreach.schemas.outreach_request import LinkedInOutreachRequest
from agents.outreach.state.outreachstate import OutreachState


async def linkedinOutreachAgent(request: LinkedInOutreachRequest) -> dict[str, Any]:
    start = time.time()
    config = request.to_agent_config()

    log_pipeline_start(
        username=request.linkedin_username,
        profile_url=request.profile_url(),
        send_connection=request.send_connection,
        send_message=request.send_message,
        has_note=bool((request.connection_note or "").strip()),
        has_message=bool((request.message or "").strip()),
        headless=request.headless,
    )

    initial_state: OutreachState = {
        "config": config,
        "linkedin_username": request.linkedin_username,
        "profile_url": request.profile_url(),
        "connection_note": config.get("connection_note") or "",
        "message": config.get("message") or "",
        "send_connection": request.send_connection,
        "send_message": request.send_message,
        "profile_opened": False,
        "connection_status": "unknown",
        "connection_sent": False,
        "note_sent": False,
        "message_sent": False,
        "already_connected": False,
        "logs": [],
    }

    try:
        final_state = await outreach_graph_app.ainvoke(initial_state)
    except Exception as exc:
        duration = round(time.time() - start, 3)
        log_pipeline_complete(
            status="failed",
            duration_sec=duration,
            error=str(exc)[:160],
        )
        return {
            "success": False,
            "error": str(exc),
            "linkedin_username": request.linkedin_username,
            "profile_url": request.profile_url(),
            "meta": {
                "duration_sec": duration,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_mode": "linkedin_outreach",
            },
        }

    duration = round(time.time() - start, 3)
    result = final_state.get("result") or {}
    error = final_state.get("error") or result.get("error")
    did_work = bool(
        final_state.get("connection_sent")
        or final_state.get("message_sent")
        or final_state.get("note_sent")
        or final_state.get("already_connected")
        or (
            final_state.get("connection_status") == "pending"
            and not error
        )
    )
    success = bool(final_state.get("profile_opened")) and did_work and not (
        error and not (final_state.get("connection_sent") or final_state.get("message_sent"))
    )
    if final_state.get("profile_opened") and not error and (
        final_state.get("send_connection") is False and final_state.get("send_message") is False
    ):
        success = True
    status = "success" if success else ("partial" if final_state.get("profile_opened") else "failed")

    log_pipeline_complete(
        status=status,
        duration_sec=duration,
        profile_opened=bool(final_state.get("profile_opened")),
        connection_status=final_state.get("connection_status"),
        connection_sent=bool(final_state.get("connection_sent")),
        note_sent=bool(final_state.get("note_sent")),
        message_sent=bool(final_state.get("message_sent")),
        already_connected=bool(final_state.get("already_connected")),
        error=(str(error)[:120] if error else None),
    )
    log_event(
        "9_complete",
        "Result summary",
        username=request.linkedin_username,
        success=success,
    )

    return {
        "success": success,
        "error": error,
        "linkedin_username": request.linkedin_username,
        "profile_url": request.profile_url(),
        "profile_opened": bool(final_state.get("profile_opened")),
        "connection_status": final_state.get("connection_status"),
        "connection_sent": bool(final_state.get("connection_sent")),
        "note_sent": bool(final_state.get("note_sent")),
        "message_sent": bool(final_state.get("message_sent")),
        "already_connected": bool(final_state.get("already_connected")),
        "result": result,
        "logs": final_state.get("logs") or [],
        "meta": {
            "duration_sec": duration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_mode": "linkedin_outreach",
            "headless": request.headless,
        },
    }
