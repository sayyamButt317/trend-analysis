from __future__ import annotations

from agents.contentgeneration.llm import complete_json
from agents.contentgeneration.pipeline_log import log_event
from agents.contentgeneration.State.generationstate import (
    VideoState,
    as_dict,
    parse_characters,
    parse_project,
    parse_scenes,
)


async def VisualPromptGeneratorNode(state: VideoState) -> VideoState:
    logs = list(state.get("logs") or [])
    project = parse_project(state.get("project"))
    characters = parse_characters(state.get("characters"))
    scenes = parse_scenes(state.get("scenes"))
    appearance = "; ".join(f"{c.name}: {c.appearance}" for c in characters if c.appearance)

    payload = await complete_json(
        system=(
            "Write image-to-video prompts. Return JSON {\"prompts\":["
            "{\"scene_number\",\"prompt\"}]}. Each prompt must keep character appearance "
            "consistent, include camera, lighting, and motion, and stay under 80 words."
        ),
        user=(
            f"Style: {project.tone or state.get('style')}\n"
            f"Aspect ratio: {project.aspect_ratio}\n"
            f"Character looks: {appearance or 'none'}\n"
            f"Scenes:\n"
            + "\n".join(
                f"{s.scene_number}. loc={s.location} camera={s.camera} "
                f"action={s.action} dialogue={'; '.join(s.dialogue)}"
                for s in scenes
            )
        ),
        temperature=0.5,
    )

    by_number: dict[int, str] = {}
    raw = payload.get("prompts") if isinstance(payload.get("prompts"), list) else []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            number = int(item.get("scene_number"))
        except (TypeError, ValueError):
            continue
        by_number[number] = str(item.get("prompt") or "").strip()

    visual_prompts: list[dict[str, str]] = []
    for scene in scenes:
        prompt = by_number.get(scene.scene_number) or (
            f"{scene.visual_style} {scene.camera} of {scene.location} at {scene.time_of_day}. "
            f"{scene.action}. Consistent characters: {appearance}."
        )
        scene.visual_prompt = prompt
        visual_prompts.append({"scene_number": str(scene.scene_number), "prompt": prompt})

    logs.append(f"visual_prompt_generator:{len(visual_prompts)}")
    log_event("2_production", "Visual prompts ready", count=len(visual_prompts))
    return {
        **state,
        "scenes": [as_dict(scene) for scene in scenes],
        "visual_prompts": visual_prompts,
        "logs": logs,
    }
