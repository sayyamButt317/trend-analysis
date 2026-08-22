from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

_VIDEO_PAYLOAD_PATH = Path(__file__).resolve().parents[3] / "video_payload.json"


def _example_payload() -> dict[str, Any]:
    if _VIDEO_PAYLOAD_PATH.is_file():
        return json.loads(_VIDEO_PAYLOAD_PATH.read_text(encoding="utf-8"))
    return {
        "user_request": "30 second product ad for Techtimize.",
        "duration_seconds": 30,
        "aspect_ratio": "16:9",
        "style": "cinematic",
        "generate_media": True,
        "project": {"name": "Techtimize: Build Faster with AI", "aspect_ratio": "16:9"},
        "script": {"title": "Techtimize: Build Faster with AI", "logline": ""},
        "characters": [{"name": "The Founder", "appearance": "Business attire"}],
        "scenes": [
            {
                "scene_number": 1,
                "duration": 5,
                "location": "Modern office exterior",
                "action": "Founder walks through glass doors.",
            }
        ],
    }


_EXAMPLE = _example_payload()


class ContentGenerationRequest(BaseModel):
    """Produce video from a script-agent result (project, script, characters, scenes)."""

    model_config = ConfigDict(json_schema_extra={"example": _EXAMPLE})

    scenes: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="Scenes from POST /script-generation/script",
        examples=[_EXAMPLE["scenes"]],
    )
    project: dict[str, Any] = Field(
        default_factory=dict,
        examples=[_EXAMPLE.get("project") or {}],
    )
    script: dict[str, Any] = Field(
        default_factory=dict,
        examples=[_EXAMPLE.get("script") or {}],
    )
    characters: list[dict[str, Any]] = Field(
        default_factory=list,
        examples=[_EXAMPLE.get("characters") or []],
    )
    user_request: str = Field(
        default="",
        description="Optional original brief for context.",
        examples=[_EXAMPLE.get("user_request") or ""],
    )
    duration_seconds: int = Field(default=30, ge=5, le=120)
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"
    style: str = Field(default="cinematic")
    generate_media: bool = Field(
        default=True,
        description="Call Higgsfield for images/video. If false, stop after visual prompts.",
    )

    def to_agent_config(self) -> dict[str, Any]:
        project = dict(self.project or {})
        return {
            "user_request": (self.user_request or "").strip(),
            "duration_seconds": int(project.get("duration_seconds") or self.duration_seconds),
            "aspect_ratio": str(project.get("aspect_ratio") or self.aspect_ratio),
            "style": self.style.strip() or "cinematic",
            "generate_media": self.generate_media,
            "project": project,
            "script": dict(self.script or {}),
            "characters": list(self.characters or []),
            "scenes": list(self.scenes),
        }
