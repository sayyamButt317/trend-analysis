from __future__ import annotations

import re
import uuid

from agents.scriptgenerator.llm import complete_json
from agents.scriptgenerator.pipeline_log import log_event
from agents.scriptgenerator.State.scriptstate import (
    Scene,
    ScriptState,
    as_dict,
    parse_characters,
    parse_project,
    parse_script,
)


def _as_int(value, default: int) -> int:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    match = re.search(r"-?\d+", str(value))
    if match:
        return int(match.group(0))
    return default


async def ScenePlannerNode(state: ScriptState) -> ScriptState:
    logs = list(state.get("logs") or [])
    project = parse_project(state.get("project"))
    script = parse_script(state.get("script"))
    characters = parse_characters(state.get("characters"))
    names = [c.name for c in characters]

    payload = await complete_json(
        system=(
            "Break a short video script into 3-8 scenes. Return JSON "
            "{\"scenes\":[{\"scene_number\",\"duration\",\"location\",\"time_of_day\","
            "\"characters\",\"dialogue\",\"narration\",\"action\",\"camera\",\"visual_style\"}]}. "
            "duration must be an integer number of seconds (e.g. 5), never a string like \"5s\". "
            f"Total duration should stay near {project.duration_seconds} seconds."
        ),
        user=(
            f"Project: {project.name}\n"
            f"Style: {state.get('style')}\n"
            f"Characters: {', '.join(names)}\n"
            f"Script:\n{script.body}"
        ),
        temperature=0.45,
    )

    raw = payload.get("scenes") if isinstance(payload.get("scenes"), list) else []
    scenes: list[Scene] = []
    for index, item in enumerate(raw[:8], start=1):
        if not isinstance(item, dict):
            continue
        dialogue = item.get("dialogue")
        if isinstance(dialogue, str):
            dialogue = [dialogue]
        if not isinstance(dialogue, list):
            dialogue = []
        char_list = item.get("characters")
        if isinstance(char_list, str):
            char_list = [char_list]
        if not isinstance(char_list, list):
            char_list = names[:1]
        scenes.append(
            Scene(
                id=str(uuid.uuid4())[:8],
                scene_number=_as_int(item.get("scene_number"), index),
                duration=max(2, _as_int(item.get("duration"), 5)),
                location=str(item.get("location") or "studio")[:120],
                time_of_day=str(item.get("time_of_day") or "day")[:40],
                characters=[str(c) for c in char_list if str(c).strip()][:6],
                dialogue=[str(d) for d in dialogue if str(d).strip()][:8],
                narration=str(item.get("narration") or "")[:400] or None,
                action=str(item.get("action") or "")[:400],
                camera=str(item.get("camera") or "medium shot")[:80],
                visual_style=str(item.get("visual_style") or state.get("style") or "cinematic")[:80],
            )
        )

    if not scenes:
        scenes.append(
            Scene(
                id=str(uuid.uuid4())[:8],
                scene_number=1,
                duration=project.duration_seconds,
                location="studio",
                time_of_day="day",
                characters=names[:1],
                action=script.logline or script.body[:200],
                camera="medium shot",
                visual_style=str(state.get("style") or "cinematic"),
            )
        )

    logs.append(f"scene_planner:{len(scenes)}")
    log_event("1_story", "Scenes planned", count=len(scenes))
    return {
        **state,
        "scenes": [as_dict(scene) for scene in scenes],
        "current_scene_index": 0,
        "logs": logs,
    }
