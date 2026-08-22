from __future__ import annotations

from agents.contentgeneration.pipeline_log import log_event
from agents.contentgeneration.State.generationstate import VideoState, as_dict, parse_scenes
from service.ContentGeneration.higgsfield import (
    generate_video,
    higgsfield_configured,
    higgsfield_import_error,
    higgsfield_keys_present,
    higgsfield_last_error,
)


async def VideoGeneratorNode(state: VideoState) -> VideoState:
    logs = list(state.get("logs") or [])
    scenes = parse_scenes(state.get("scenes"))
    aspect = state.get("aspect_ratio") or (state.get("project") or {}).get("aspect_ratio") or "16:9"
    clips: list[dict[str, str | int | None]] = list(state.get("generated_videos") or [])

    if not state.get("generate_media", True):
        logs.append("video_generator:skipped_generate_media=false")
        log_event("2_production", "Video generation skipped", reason="generate_media=false")
        return {**state, "generated_videos": clips, "logs": logs}

    if not higgsfield_keys_present():
        message = (
            "Higgsfield API keys missing. Set HIGGSFIELD_API_KEY_ID and "
            "HIGGSFIELD_API_KEY_SECRET."
        )
        logs.append("video_generator:skipped_no_credentials")
        log_event("2_production", "Video generation skipped", reason="no_credentials")
        return {
            **state,
            "generated_videos": clips,
            "logs": logs,
            "error": state.get("error") or message,
        }

    if not higgsfield_configured():
        message = higgsfield_import_error() or "Higgsfield client is not available."
        logs.append("video_generator:skipped_client_missing")
        log_event("2_production", "Video generation skipped", reason="client_missing")
        return {
            **state,
            "generated_videos": clips,
            "logs": logs,
            "error": state.get("error") or message,
        }

    for scene in scenes:
        prompt = scene.visual_prompt or scene.action
        if not prompt:
            continue
        if not scene.image_url:
            logs.append(f"video_generator:skipped_no_still_scene_{scene.scene_number}")
            log_event(
                "2_production",
                "Skipping scene video; still required",
                scene=scene.scene_number,
            )
            continue
        log_event(
            "2_production",
            "Generating scene video",
            scene=scene.scene_number,
            has_image=True,
        )
        url = await generate_video(
            prompt,
            image_url=scene.image_url,
            aspect_ratio=aspect,
        )
        if url:
            scene.video_url = url
            clips.append(
                {
                    "scene_number": scene.scene_number,
                    "url": url,
                    "duration": scene.duration,
                }
            )
            logs.append(f"video_generator:scene_{scene.scene_number}")
        else:
            logs.append(f"video_generator:failed_scene_{scene.scene_number}")

    log_event("2_production", "Scene videos generated", count=len(clips))
    error = state.get("error")
    if clips:
        error = None
    elif not error:
        detail = higgsfield_last_error()
        error = (
            "Higgsfield generated no videos. Image-to-video needs a still "
            "(image_url) for each scene. "
            + (detail or "Check credits and HIGGSFIELD_VIDEO_MODEL.")
        )
    return {
        **state,
        "scenes": [as_dict(scene) for scene in scenes],
        "generated_videos": clips,
        "logs": logs,
        "error": error,
    }
