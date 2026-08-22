from __future__ import annotations
from agents.contentgeneration.pipeline_log import log_event
from agents.contentgeneration.State.generationstate import VideoState, parse_characters, parse_scenes


async def AssetManagerNode(state: VideoState) -> VideoState:
    logs = list(state.get("logs") or [])
    characters = parse_characters(state.get("characters"))
    scenes = parse_scenes(state.get("scenes"))
    assets = dict(state.get("generated_assets") or {})

    assets["characters"] = [
        {
            "id": character.id,
            "name": character.name,
            "appearance": character.appearance,
            "reference_image_url": character.reference_image_url,
        }
        for character in characters
    ]
    assets["scenes"] = [
        {
            "id": scene.id,
            "scene_number": scene.scene_number,
            "location": scene.location,
            "needs_image": not scene.image_url,
            "needs_video": not scene.video_url,
        }
        for scene in scenes
    ]
    logs.append(f"asset_manager:chars={len(characters)} scenes={len(scenes)}")
    log_event(
        "2_production",
        "Asset slots prepared",
        characters=len(characters),
        scenes=len(scenes),
    )
    return {**state, "generated_assets": assets, "logs": logs}
