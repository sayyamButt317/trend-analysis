from __future__ import annotations
from agents.outreach.pipeline_log import log_event
from agents.outreach.state.outreachstate import OutreachState


async def note_node(state: OutreachState) -> OutreachState:
    logs = list(state.get("logs") or [])
    if state.get("note_sent"):
        logs.append("note_step:sent_with_invitation")
        log_event("3_note", "Connection note sent with invitation")
    elif (state.get("connection_note") or "").strip():
        logs.append("note_step:requested_but_not_confirmed")
        log_event("3_note", "Note was requested but not confirmed")
    else:
        logs.append("note_step:skipped_no_note")
        log_event("3_note", "No connection note provided — skipped")
    return {**state, "logs": logs}


NoteNode = note_node
