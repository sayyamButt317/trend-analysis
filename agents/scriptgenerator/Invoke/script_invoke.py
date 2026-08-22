from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from agents.scriptgenerator.Graph.script_graph import script_generator_app
from agents.scriptgenerator.pipeline_log import log_event, log_pipeline_complete, log_pipeline_start
from agents.scriptgenerator.schemas.script_request import ScriptGenerationRequest
from agents.scriptgenerator.State.scriptstate import ScriptState


async def scriptGenerationAgent(request: ScriptGenerationRequest) -> dict[str, Any]:
    start = time.time()
    config = request.to_agent_config()

    log_pipeline_start(
        user_request=request.user_request,
        duration_seconds=request.duration_seconds,
        aspect_ratio=request.aspect_ratio,
        style=request.style,
    )

    initial_state: ScriptState = {
        "user_request": config["user_request"],
        "duration_seconds": config["duration_seconds"],
        "aspect_ratio": config["aspect_ratio"],
        "style": config["style"],
        "project": {},
        "script": {},
        "characters": [],
        "scenes": [],
        "current_scene_index": 0,
        "error": None,
        "logs": [],
    }

    try:
        final_state = await script_generator_app.ainvoke(initial_state)
    except Exception as exc:
        duration = round(time.time() - start, 3)
        log_pipeline_complete(status="failed", duration_sec=duration, error=str(exc)[:160])
        return {
            "success": False,
            "error": str(exc),
            "meta": {
                "duration_sec": duration,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_mode": "script_generation",
            },
        }

    duration = round(time.time() - start, 3)
    error = final_state.get("error")
    scenes = final_state.get("scenes") or []
    success = not error and bool(scenes)
    status = "success" if success else ("partial" if scenes else "failed")

    log_pipeline_complete(
        status=status,
        duration_sec=duration,
        scenes=len(scenes),
        characters=len(final_state.get("characters") or []),
        error=(str(error)[:120] if error else None),
    )
    log_event("9_complete", "Result summary", success=success, scenes=len(scenes))

    return {
        "success": success,
        "error": error,
        "project": final_state.get("project") or {},
        "script": final_state.get("script") or {},
        "characters": final_state.get("characters") or [],
        "scenes": scenes,
        "logs": final_state.get("logs") or [],
        "meta": {
            "duration_sec": duration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_mode": "script_generation",
            "aspect_ratio": request.aspect_ratio,
            "style": request.style,
            "duration_seconds": request.duration_seconds,
        },
    }
