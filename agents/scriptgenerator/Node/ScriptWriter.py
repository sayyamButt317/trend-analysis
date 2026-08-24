from __future__ import annotations

import uuid
from datetime import datetime, timezone

from agents.scriptgenerator.llm import complete_json
from agents.scriptgenerator.pipeline_log import log_event
from agents.scriptgenerator.State.scriptstate import Script, ScriptState, as_dict, parse_project


def _suggestion(state: ScriptState) -> dict:
    value = state.get("content_suggestion") or {}
    return value if isinstance(value, dict) else {}


async def ScriptWriterNode(state: ScriptState) -> ScriptState:
    logs = list(state.get("logs") or [])
    project = parse_project(state.get("project"))
    request = state.get("user_request") or project.description
    content_type = (
        state.get("content_type")
        or getattr(project, "content_type", None)
        or "video"
    ).strip().lower()
    if content_type not in {"image", "video"}:
        content_type = "video"
    suggestion = _suggestion(state)

    if content_type == "image":
        system = (
            "You write a social IMAGE/CAROUSEL script. Return JSON with keys: "
            "title, logline, hook, caption, cta, body. "
            "body should list slide-by-slide copy for still images (not timed video beats)."
        )
        user = (
            f"Project: {project.name}\n"
            f"Platform: {project.platform or suggestion.get('platform')}\n"
            f"Format: {project.format or suggestion.get('format')}\n"
            f"Description: {project.description}\n"
            f"Audience: {project.audience}\n"
            f"Tone: {project.tone}\n"
            f"Style: {state.get('style')}\n"
            f"Suggestion: {suggestion}\n"
            f"Original request: {request}"
        )
    else:
        system = (
            "You write a short video script. Return JSON with keys: "
            "title, logline, hook, caption, cta, body. Body should include timed beats for a "
            f"{project.duration_seconds}s video."
        )
        user = (
            f"Project: {project.name}\n"
            f"Description: {project.description}\n"
            f"Audience: {project.audience}\n"
            f"Tone: {project.tone}\n"
            f"Style: {state.get('style')}\n"
            f"Suggestion: {suggestion}\n"
            f"Original request: {request}"
        )

    payload = await complete_json(system=system, user=user, temperature=0.6)

    now = datetime.now(timezone.utc)
    title = str(
        payload.get("title")
        or suggestion.get("title")
        or project.name
    )[:120]
    hook = str(payload.get("hook") or suggestion.get("hook") or "")[:280]
    caption = str(payload.get("caption") or suggestion.get("caption") or "")[:1200]
    cta = str(payload.get("cta") or suggestion.get("cta") or "")[:200]
    body = str(payload.get("body") or caption or request)
    script = Script(
        id=str(uuid.uuid4())[:8],
        title=title,
        logline=str(payload.get("logline") or hook or "")[:280],
        body=body,
        caption=caption,
        hook=hook,
        cta=cta,
        content_type=content_type,
        created_at=now,
        updated_at=now,
    )
    logs.append(f"script_writer:{script.title}:{content_type}")
    log_event("1_story", "Script drafted", title=script.title, content_type=content_type)
    return {**state, "script": as_dict(script), "content_type": content_type, "logs": logs}
