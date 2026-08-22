from __future__ import annotations
import time
from datetime import datetime, timezone
from typing import Any
from agents.contentgeneration.Graph.generation_graph import content_generation_app
from agents.contentgeneration.pipeline_log import (
    log_event,
    log_pipeline_complete,
    log_pipeline_start,
)
from agents.contentgeneration.schemas.generation_request import ContentGenerationRequest
from agents.contentgeneration.State.generationstate import VideoState


async def contentGenerationAgent(request: ContentGenerationRequest) -> dict[str, Any]:
    start = time.time()
    config = request.to_agent_config()

    log_pipeline_start(
        user_request=config.get("user_request") or "",
        duration_seconds=config["duration_seconds"],
        aspect_ratio=config["aspect_ratio"],
        style=config["style"],
        generate_media=config["generate_media"],
        scenes=len(config.get("scenes") or []),
    )

    initial_state: VideoState = {
        "user_request": config.get("user_request") or "",
        "duration_seconds": config["duration_seconds"],
        "aspect_ratio": config["aspect_ratio"],
        "style": config["style"],
        "generate_media": bool(config.get("generate_media", True)),
        "project": config.get("project") or {},
        "script": config.get("script") or {},
        "characters": config.get("characters") or [],
        "scenes": config.get("scenes") or [],
        "current_scene_index": 0,
        "generated_assets": {},
        "visual_prompts": [],
        "generated_videos": [],
        "validation_errors": [],
        "final_video_url": None,
        "error": None,
        "logs": [],
    }

    try:
        final_state = await content_generation_app.ainvoke(initial_state)
    except Exception as exc:
        duration = round(time.time() - start, 3)
        log_pipeline_complete(status="failed", duration_sec=duration, error=str(exc)[:160])
        return {
            "success": False,
            "error": str(exc),
            "meta": {
                "duration_sec": duration,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_mode": "content_generation",
            },
        }

    duration = round(time.time() - start, 3)
    error = final_state.get("error")
    final_url = final_state.get("final_video_url")
    videos = final_state.get("generated_videos") or []
    prompts = final_state.get("visual_prompts") or []
    if config.get("generate_media"):
        success = not error and bool(videos or final_url)
    else:
        success = not error and bool(prompts)
    status = "success" if success else ("partial" if prompts else "failed")

    log_pipeline_complete(
        status=status,
        duration_sec=duration,
        scenes=len(final_state.get("scenes") or []),
        videos=len(videos),
        has_final=bool(final_url),
        error=(str(error)[:120] if error else None),
    )
    log_event("9_complete", "Result summary", success=success, final_video=bool(final_url))

    return {
        "success": success,
        "error": error,
        "project": final_state.get("project") or {},
        "script": final_state.get("script") or {},
        "characters": final_state.get("characters") or [],
        "scenes": final_state.get("scenes") or [],
        "visual_prompts": prompts,
        "generated_assets": final_state.get("generated_assets") or {},
        "generated_videos": videos,
        "validation_errors": final_state.get("validation_errors") or [],
        "final_video_url": final_url,
        "logs": final_state.get("logs") or [],
        "meta": {
            "duration_sec": duration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_mode": "content_generation",
            "aspect_ratio": config["aspect_ratio"],
            "style": config["style"],
            "duration_seconds": config["duration_seconds"],
        },
    }
