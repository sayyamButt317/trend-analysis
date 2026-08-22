from __future__ import annotations

from typing import Any, TypedDict

from agents.scriptgenerator.State.scriptstate import (
    Character,
    Project,
    Scene,
    Script,
    as_dict,
    parse_characters,
    parse_project,
    parse_scenes,
    parse_script,
)

__all__ = [
    "Character",
    "Project",
    "Scene",
    "Script",
    "VideoState",
    "as_dict",
    "parse_characters",
    "parse_project",
    "parse_scenes",
    "parse_script",
]


class VideoState(TypedDict, total=False):
    """LangGraph state for the video production pipeline."""

    user_request: str
    duration_seconds: int
    aspect_ratio: str
    style: str
    generate_media: bool

    project: dict[str, Any]
    script: dict[str, Any]
    characters: list[dict[str, Any]]
    scenes: list[dict[str, Any]]
    current_scene_index: int

    generated_assets: dict[str, Any]
    visual_prompts: list[dict[str, Any]]
    generated_videos: list[dict[str, Any]]
    validation_errors: list[str]
    final_video_url: str | None

    error: str | None
    logs: list[str]
