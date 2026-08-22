from __future__ import annotations
from agents.contentgeneration.pipeline_log import log_event
from agents.contentgeneration.State.generationstate import VideoState, parse_scenes


async def VideoQualityCheckerNode(state: VideoState) -> VideoState:
    logs = list(state.get("logs") or [])
    scenes = parse_scenes(state.get("scenes"))
    clips = list(state.get("generated_videos") or [])
    errors: list[str] = []

    if not scenes:
        errors.append("No scenes were planned.")
    for scene in scenes:
        if not (scene.visual_prompt or scene.action):
            errors.append(f"Scene {scene.scene_number} is missing a visual prompt.")
        if state.get("generate_media", True) and not scene.video_url and not scene.image_url:
            errors.append(f"Scene {scene.scene_number} has no generated media.")

    final_url = None
    if clips:
        final_url = str(clips[-1].get("url") or "") or None
    elif scenes:
        final_url = next((s.video_url or s.image_url for s in scenes if s.video_url or s.image_url), None)

    if not final_url and state.get("generate_media", True):
        errors.append("No final video or still was produced.")

    logs.append(f"post_production:errors={len(errors)}")
    log_event(
        "3_post",
        "Post production finished",
        clips=len(clips),
        errors=len(errors),
        has_final=bool(final_url),
    )
    return {
        **state,
        "validation_errors": errors,
        "final_video_url": final_url,
        "error": errors[0] if errors and not final_url else state.get("error"),
        "logs": logs,
    }
