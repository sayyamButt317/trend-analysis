from __future__ import annotations
import logging
from agents.outreach.state.outreachstate import OutreachState
from service.Outreach.linkedin_outreach import run_linkedin_outreach

logger = logging.getLogger(__name__)


async def open_profile_node(state: OutreachState) -> OutreachState:
    if state.get("error"):
        return state

    config = state.get("config") or {}
    username = state.get("linkedin_username") or config.get("linkedin_username") or ""
    profile_url = state.get("profile_url") or config.get("profile_url") or ""
    if not profile_url and username:
        profile_url = f"https://www.linkedin.com/in/{username}/"

    logs = list(state.get("logs") or [])
    logs.append(f"opening_profile:{profile_url}")

    result = await run_linkedin_outreach(
        profile_url=profile_url,
        connection_note=state.get("connection_note") or config.get("connection_note") or "",
        message=state.get("message") or config.get("message") or "",
        send_connection=bool(state.get("send_connection", config.get("send_connection", True))),
        send_message=bool(state.get("send_message", config.get("send_message", True))),
        headless=bool(config.get("headless", True)),
    )

    logs.extend(result.get("logs") or [])
    return {
        **state,
        "profile_url": profile_url,
        "profile_opened": bool(result.get("profile_opened")),
        "connection_status": result.get("connection_status") or "unknown",
        "connection_sent": bool(result.get("connection_sent")),
        "note_sent": bool(result.get("note_sent")),
        "message_sent": bool(result.get("message_sent")),
        "already_connected": bool(result.get("already_connected")),
        "result": {
            "username": username,
            "profile_url": profile_url,
            "profile_opened": bool(result.get("profile_opened")),
            "connection_status": result.get("connection_status") or "unknown",
            "connection_sent": bool(result.get("connection_sent")),
            "note_sent": bool(result.get("note_sent")),
            "message_sent": bool(result.get("message_sent")),
            "already_connected": bool(result.get("already_connected")),
            "error": result.get("error"),
            "details": result.get("details") or {},
        },
        "error": result.get("error"),
        "logs": logs,
    }


OpenProfileNode = open_profile_node
