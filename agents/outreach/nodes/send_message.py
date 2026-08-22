from __future__ import annotations

from agents.outreach.pipeline_log import log_event
from agents.outreach.state.outreachstate import OutreachState


async def send_message_node(state: OutreachState) -> OutreachState:
    logs = list(state.get("logs") or [])
    if state.get("message_sent"):
        logs.append("message_step:sent")
        log_event("4_message", "Direct message sent")
    elif state.get("note_sent") and (state.get("connection_note") or "").strip():
        logs.append("message_step:covered_by_connection_note")
        log_event("4_message", "DM skipped — connection note already used")
    elif state.get("send_message") is False:
        logs.append("message_step:skipped")
        log_event("4_message", "Message skipped by request")
    elif not (state.get("message") or "").strip():
        logs.append("message_step:skipped_empty_message")
        log_event("4_message", "No message body provided — skipped")
    else:
        logs.append("message_step:not_sent")
        log_event(
            "4_message",
            "Message was not sent",
            connection_status=state.get("connection_status"),
            error=str(state.get("error") or "")[:120] or None,
        )
    return {**state, "logs": logs}


SendMessageNode = send_message_node
