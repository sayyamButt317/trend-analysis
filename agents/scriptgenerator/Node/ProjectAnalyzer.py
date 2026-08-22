from __future__ import annotations

import uuid
from datetime import datetime, timezone

from agents.scriptgenerator.llm import complete_json
from agents.scriptgenerator.pipeline_log import log_event
from agents.scriptgenerator.State.scriptstate import Project, ScriptState, as_dict


async def ProjectAnalyzerNode(state: ScriptState) -> ScriptState:
    logs = list(state.get("logs") or [])
    request = (state.get("user_request") or "").strip()
    duration = int(state.get("duration_seconds") or 30)
    aspect = state.get("aspect_ratio") or "16:9"
    style = state.get("style") or "cinematic"

    payload = await complete_json(
        system=(
            "You turn a video brief into a compact project JSON. "
            "Return keys: name, description, audience, tone."
        ),
        user=(
            f"Brief: {request}\n"
            f"Target duration: {duration}s\n"
            f"Aspect ratio: {aspect}\n"
            f"Style: {style}"
        ),
    )

    now = datetime.now(timezone.utc)
    project = Project(
        id=str(uuid.uuid4())[:8],
        name=str(payload.get("name") or "Untitled video")[:80],
        description=str(payload.get("description") or request)[:800],
        audience=str(payload.get("audience") or "general")[:120],
        tone=str(payload.get("tone") or style)[:80],
        duration_seconds=duration,
        aspect_ratio=aspect,
        created_at=now,
        updated_at=now,
    )
    logs.append(f"project_analyzer:{project.name}")
    log_event("1_story", "Project brief ready", name=project.name, duration=duration)
    return {**state, "project": as_dict(project), "logs": logs}
