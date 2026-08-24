from __future__ import annotations

import re
import uuid
from typing import Any

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


def _as_int(value: Any, default: int) -> int:
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


def _suggestion(state: ScriptState) -> dict[str, Any]:
    value = state.get("content_suggestion") or {}
    return value if isinstance(value, dict) else {}


def _scenes_from_suggestion_slides(
    *,
    suggestion: dict[str, Any],
    style: str,
    content_type: str,
) -> list[Scene]:
    slides = suggestion.get("slides") if isinstance(suggestion.get("slides"), list) else []
    scenes: list[Scene] = []
    for index, slide in enumerate(slides[:8], start=1):
        if not isinstance(slide, dict):
            continue
        headline = str(slide.get("headline") or slide.get("title") or suggestion.get("title") or "").strip()
        body = str(slide.get("body") or slide.get("text") or "").strip()
        prompt = str(
            slide.get("image_prompt")
            or slide.get("visual_prompt")
            or suggestion.get("image_prompt")
            or f"{style}. {headline}. {body}"
        ).strip()
        scenes.append(
            Scene(
                id=str(uuid.uuid4())[:8],
                scene_number=_as_int(slide.get("slide_number"), index),
                duration=1 if content_type == "image" else 5,
                location=str(suggestion.get("platform") or "social")[:120],
                time_of_day="day",
                characters=["Brand Visual"] if content_type == "image" else [],
                dialogue=[],
                narration=body[:400] or None,
                action=body or headline,
                camera="static frame" if content_type == "image" else "medium shot",
                visual_style=style[:80],
                visual_prompt=prompt[:500],
                media_type=content_type,
                headline=headline[:120],
                body_text=body[:400],
            )
        )
    return scenes


async def ScenePlannerNode(state: ScriptState) -> ScriptState:
    logs = list(state.get("logs") or [])
    project = parse_project(state.get("project"))
    script = parse_script(state.get("script"))
    characters = parse_characters(state.get("characters"))
    names = [c.name for c in characters]
    content_type = (state.get("content_type") or project.content_type or "video").strip().lower()
    if content_type not in {"image", "video"}:
        content_type = "video"
    suggestion = _suggestion(state)
    style = str(state.get("style") or project.tone or "cinematic")

    # Prefer calendar-provided slides for image jobs.
    if content_type == "image":
        seeded = _scenes_from_suggestion_slides(
            suggestion=suggestion,
            style=style,
            content_type=content_type,
        )
        if seeded:
            logs.append(f"scene_planner:image_slides:{len(seeded)}")
            log_event("1_story", "Image slides planned", count=len(seeded))
            return {
                **state,
                "scenes": [as_dict(scene) for scene in seeded],
                "current_scene_index": 0,
                "logs": logs,
            }

        payload = await complete_json(
            system=(
                "Break an image/carousel brief into 1-8 still frames. Return JSON "
                "{\"scenes\":[{\"scene_number\",\"headline\",\"body_text\",\"visual_prompt\","
                "\"location\",\"action\",\"visual_style\"}]}. "
                "Each scene is one still image or carousel slide, not a timed video shot."
            ),
            user=(
                f"Project: {project.name}\n"
                f"Style: {style}\n"
                f"Aspect ratio: {project.aspect_ratio}\n"
                f"Caption: {script.caption or script.body}\n"
                f"Hook: {script.hook}\n"
                f"CTA: {script.cta}\n"
                f"Suggestion: {suggestion}\n"
                f"Script:\n{script.body}"
            ),
            temperature=0.45,
        )
    else:
        payload = await complete_json(
            system=(
                "Break a short video script into 3-8 scenes. Return JSON "
                "{\"scenes\":[{\"scene_number\",\"duration\",\"location\",\"time_of_day\","
                "\"characters\",\"dialogue\",\"narration\",\"action\",\"camera\",\"visual_style\","
                "\"visual_prompt\"}]}. "
                "duration must be an integer number of seconds (e.g. 5), never a string like \"5s\". "
                f"Total duration should stay near {project.duration_seconds} seconds."
            ),
            user=(
                f"Project: {project.name}\n"
                f"Style: {style}\n"
                f"Characters: {', '.join(names)}\n"
                f"Suggestion: {suggestion}\n"
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
        headline = str(item.get("headline") or item.get("title") or "")[:120]
        body_text = str(item.get("body_text") or item.get("body") or item.get("narration") or "")[:400]
        visual_prompt = str(
            item.get("visual_prompt")
            or item.get("image_prompt")
            or suggestion.get("image_prompt")
            or ""
        ).strip()
        if not visual_prompt:
            visual_prompt = (
                f"{style} still of {item.get('location') or 'studio'}: "
                f"{headline or item.get('action') or script.title}"
            )
        scenes.append(
            Scene(
                id=str(uuid.uuid4())[:8],
                scene_number=_as_int(item.get("scene_number"), index),
                duration=max(
                    1,
                    _as_int(
                        item.get("duration"),
                        1 if content_type == "image" else 5,
                    ),
                ),
                location=str(item.get("location") or suggestion.get("platform") or "studio")[:120],
                time_of_day=str(item.get("time_of_day") or "day")[:40],
                characters=[str(c) for c in char_list if str(c).strip()][:6],
                dialogue=[str(d) for d in dialogue if str(d).strip()][:8],
                narration=str(item.get("narration") or body_text or "")[:400] or None,
                action=str(item.get("action") or body_text or headline)[:400],
                camera=str(
                    item.get("camera")
                    or ("static frame" if content_type == "image" else "medium shot")
                )[:80],
                visual_style=str(item.get("visual_style") or style)[:80],
                visual_prompt=visual_prompt[:500],
                media_type=content_type,
                headline=headline,
                body_text=body_text,
            )
        )

    if not scenes:
        prompt = str(
            suggestion.get("image_prompt")
            or f"{style}. {script.title}. {script.hook or script.logline}"
        )
        scenes.append(
            Scene(
                id=str(uuid.uuid4())[:8],
                scene_number=1,
                duration=1 if content_type == "image" else project.duration_seconds,
                location=str(suggestion.get("platform") or "studio"),
                time_of_day="day",
                characters=names[:1],
                action=script.logline or script.body[:200],
                camera="static frame" if content_type == "image" else "medium shot",
                visual_style=style,
                visual_prompt=prompt[:500],
                media_type=content_type,
                headline=str(suggestion.get("title") or script.title)[:120],
                body_text=str(script.caption or script.body)[:400],
            )
        )

    logs.append(f"scene_planner:{content_type}:{len(scenes)}")
    log_event("1_story", "Scenes planned", count=len(scenes), content_type=content_type)
    return {
        **state,
        "scenes": [as_dict(scene) for scene in scenes],
        "current_scene_index": 0,
        "logs": logs,
    }
