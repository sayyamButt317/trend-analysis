from __future__ import annotations

from agents.outreach.pipeline_log import log_event
from agents.outreach.state.outreachstate import OutreachState


async def connect_node(state: OutreachState) -> OutreachState:
    logs = list(state.get("logs") or [])
    if state.get("connection_sent"):
        logs.append("connect_step:invitation_sent")
        log_event("2_connect", "Connection request sent", status="pending")
    elif state.get("already_connected"):
        logs.append("connect_step:already_connected")
        log_event("2_connect", "Already connected — no invite needed")
    elif state.get("connection_status") == "pending":
        logs.append("connect_step:already_pending")
        log_event("2_connect", "Invitation already pending")
    elif state.get("send_connection") is False:
        logs.append("connect_step:skipped")
        log_event("2_connect", "Connect skipped by request")
    else:
        logs.append("connect_step:not_sent")
        log_event(
            "2_connect",
            "Connection was not sent",
            error=str(state.get("error") or "")[:120] or None,
        )
    return {**state, "logs": logs}


ConnectNode = connect_node
