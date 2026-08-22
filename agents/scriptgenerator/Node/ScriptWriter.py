from __future__ import annotations

import uuid
from datetime import datetime, timezone

from agents.scriptgenerator.llm import complete_json
from agents.scriptgenerator.pipeline_log import log_event
from agents.scriptgenerator.State.scriptstate import Script, ScriptState, as_dict, parse_project


async def ScriptWriterNode(state: ScriptState) -> ScriptState:
    logs = list(state.get("logs") or [])
    project = parse_project(state.get("project"))
    request = state.get("user_request") or project.description

    payload = await complete_json(
        system=(
            "You write a short video script. Return JSON with keys: "
            "title, logline, body. Body should include timed beats for a "
            f"{project.duration_seconds}s video."
        ),
        user=(
            f"Project: {project.name}\n"
            f"Description: {project.description}\n"
            f"Audience: {project.audience}\n"
            f"Tone: {project.tone}\n"
            f"Style: {state.get('style')}\n"
            f"Original request: {request}"
        ),
        temperature=0.6,
    )

    now = datetime.now(timezone.utc)
    script = Script(
        id=str(uuid.uuid4())[:8],
        title=str(payload.get("title") or project.name)[:120],
        logline=str(payload.get("logline") or "")[:280],
        body=str(payload.get("body") or request),
        created_at=now,
        updated_at=now,
    )
    logs.append(f"script_writer:{script.title}")
    log_event("1_story", "Script drafted", title=script.title)
    return {**state, "script": as_dict(script), "logs": logs}
