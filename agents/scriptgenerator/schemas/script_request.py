from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ScriptGenerationRequest(BaseModel):
    user_request: str = Field(
        ...,
        min_length=8,
        description="What video to write, e.g. '30s product ad for an AI coding tool'.",
    )
    duration_seconds: int = Field(default=30, ge=5, le=120)
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"
    style: str = Field(default="cinematic")

    def to_agent_config(self) -> dict[str, Any]:
        return {
            "user_request": self.user_request.strip(),
            "duration_seconds": self.duration_seconds,
            "aspect_ratio": self.aspect_ratio,
            "style": self.style.strip() or "cinematic",
        }
