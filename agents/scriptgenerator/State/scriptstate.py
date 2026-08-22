from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict

from pydantic import BaseModel, Field


class Project(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""
    audience: str = ""
    tone: str = ""
    duration_seconds: int = 30
    aspect_ratio: str = "16:9"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Script(BaseModel):
    id: str = ""
    title: str = ""
    logline: str = ""
    body: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Character(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""
    appearance: str = ""
    personality: str = ""
    voice: str | None = None
    reference_image_url: str | None = None


class Scene(BaseModel):
    id: str = ""
    scene_number: int = 1
    duration: int = 5
    location: str = ""
    time_of_day: str = ""
    characters: list[str] = Field(default_factory=list)
    dialogue: list[str] = Field(default_factory=list)
    narration: str | None = None
    action: str = ""
    camera: str = ""
    visual_style: str = ""
    visual_prompt: str = ""
    image_url: str | None = None
    video_url: str | None = None


class ScriptState(TypedDict, total=False):
    user_request: str
    duration_seconds: int
    aspect_ratio: str
    style: str
    project: dict[str, Any]
    script: dict[str, Any]
    characters: list[dict[str, Any]]
    scenes: list[dict[str, Any]]
    current_scene_index: int
    error: str | None
    logs: list[str]


def as_dict(model: BaseModel | dict[str, Any] | None) -> dict[str, Any]:
    if model is None:
        return {}
    if isinstance(model, dict):
        return model
    return model.model_dump(mode="json")


def parse_project(value: Any) -> Project:
    if isinstance(value, Project):
        return value
    if isinstance(value, dict):
        return Project.model_validate(value)
    return Project()


def parse_script(value: Any) -> Script:
    if isinstance(value, Script):
        return value
    if isinstance(value, dict):
        return Script.model_validate(value)
    return Script()


def parse_characters(value: Any) -> list[Character]:
    items = value if isinstance(value, list) else []
    return [
        item if isinstance(item, Character) else Character.model_validate(item)
        for item in items
        if item
    ]


def parse_scenes(value: Any) -> list[Scene]:
    items = value if isinstance(value, list) else []
    return [
        item if isinstance(item, Scene) else Scene.model_validate(item)
        for item in items
        if item
    ]
