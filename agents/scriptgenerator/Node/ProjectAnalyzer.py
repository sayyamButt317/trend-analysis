from __future__ import annotations

import uuid
from datetime import datetime, timezone

from agents.scriptgenerator.llm import complete_json
from agents.scriptgenerator.pipeline_log import log_event
from agents.scriptgenerator.State.scriptstate import Project, ScriptState, as_dict


def _suggestion(state: ScriptState) -> dict:
    value = state.get("content_suggestion") or {}
    return value if isinstance(value, dict) else {}


async def ProjectAnalyzerNode(state: ScriptState) -> ScriptState:
    logs = list(state.get("logs") or [])
    request = (state.get("user_request") or "").strip()
    duration = int(state.get("duration_seconds") or 30)
    aspect = state.get("aspect_ratio") or "16:9"
    style = state.get("style") or "cinematic"
    content_type = (state.get("content_type") or "video").strip().lower()
    if content_type not in {"image", "video"}:
        content_type = "video"
    suggestion = _suggestion(state)

    payload = await complete_json(
        system=(
            f"You turn a {'image/carousel' if content_type == 'image' else 'video'} brief "
            "into a compact project JSON. Return keys: name, description, audience, tone."
        ),
        user=(
            f"Brief: {request}\n"
            f"Content type: {content_type}\n"
            f"Target duration: {duration}s\n"
            f"Aspect ratio: {aspect}\n"
            f"Style: {style}\n"
            f"Content suggestion: {suggestion}"
        ),
    )

    now = datetime.now(timezone.utc)
    default_name = (
        str(suggestion.get("title") or suggestion.get("topic") or "").strip()
        or ("Untitled image set" if content_type == "image" else "Untitled video")
    )
    project = Project(
        id=str(uuid.uuid4())[:8],
        name=str(payload.get("name") or default_name)[:80],
        description=str(payload.get("description") or request)[:800],
        audience=str(
            payload.get("audience")
            or suggestion.get("target_audience")
            or "general"
        )[:120],
        tone=str(payload.get("tone") or style)[:80],
        duration_seconds=duration,
        aspect_ratio=aspect,
        content_type=content_type,
        platform=str(suggestion.get("platform") or "")[:40],
        format=str(suggestion.get("format") or "")[:60],
        created_at=now,
        updated_at=now,
    )
    logs.append(f"project_analyzer:{project.name}:{content_type}")
    log_event(
        "1_story",
        "Project brief ready",
        name=project.name,
        duration=duration,
        content_type=content_type,
    )
    return {**state, "project": as_dict(project), "content_type": content_type, "logs": logs}
