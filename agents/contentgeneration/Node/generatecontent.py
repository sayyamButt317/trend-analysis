from __future__ import annotations
from agents.contentgeneration.pipeline_log import log_event
from agents.contentgeneration.State.generationstate import VideoState, parse_scenes
from service.ContentGeneration.higgsfield import (
    generate_image,
    higgsfield_configured,
    higgsfield_import_error,
    higgsfield_keys_present,
    higgsfield_last_error,
)


async def HiggsfieldNode(state: VideoState) -> VideoState:
    logs = list(state.get("logs") or [])
    scenes = parse_scenes(state.get("scenes"))
    assets = dict(state.get("generated_assets") or {})
    aspect = state.get("aspect_ratio") or (state.get("project") or {}).get("aspect_ratio") or "16:9"

    if not state.get("generate_media", True):
        logs.append("higgsfield:skipped_generate_media=false")
        log_event("2_production", "Higgsfield skipped", reason="generate_media=false")
        return {**state, "logs": logs, "generated_assets": assets}

    if not higgsfield_keys_present():
        message = (
            "Higgsfield API keys missing. Set HIGGSFIELD_API_KEY_ID and "
            "HIGGSFIELD_API_KEY_SECRET (or HIGGSFEED_API_KEY_ID / HIGGSFEED_API_KEY_SECRET)."
        )
        logs.append("higgsfield:skipped_no_credentials")
        log_event("2_production", "Higgsfield skipped", reason="no_credentials")
        return {**state, "logs": logs, "generated_assets": assets, "error": message}

    if not higgsfield_configured():
        message = higgsfield_import_error() or "Higgsfield client is not available."
        logs.append("higgsfield:skipped_client_missing")
        log_event("2_production", "Higgsfield skipped", reason="client_missing")
        return {**state, "logs": logs, "generated_assets": assets, "error": message}

    image_urls: list[str] = list(assets.get("images") or [])
    for scene in scenes:
        prompt = scene.visual_prompt or scene.action or scene.location
        if not prompt:
            continue
        log_event("2_production", "Generating still", scene=scene.scene_number)
        url = await generate_image(prompt, aspect_ratio=aspect)
        if url:
            scene.image_url = url
            image_urls.append(url)
            logs.append(f"higgsfield:image_scene_{scene.scene_number}")
        else:
            logs.append(f"higgsfield:image_failed_scene_{scene.scene_number}")
            detail = (higgsfield_last_error() or "").lower()
            if "credit" in detail:
                logs.append("higgsfield:stopped_no_credits")
                break

    assets["images"] = image_urls
    log_event("2_production", "Higgsfield stills generated", count=len(image_urls))
    error = state.get("error")
    if not image_urls:
        detail = higgsfield_last_error()
        error = (
            "Higgsfield generated no stills. "
            + (detail or "Check API keys, credits, and model access.")
        )
    return {
        **state,
        "scenes": [scene.model_dump(mode="json") for scene in scenes],
        "generated_assets": assets,
        "logs": logs,
        "error": error,
    }
