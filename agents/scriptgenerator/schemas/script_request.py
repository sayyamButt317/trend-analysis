from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScriptGenerationRequest(BaseModel):
    """Create an image or video production script from a brief or calendar suggestion."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "content_type": "image",
                "user_request": "LinkedIn carousel about AI agents for SME founders",
                "duration_seconds": 5,
                "aspect_ratio": "1:1",
                "style": "clean modern social graphic",
                "content_suggestion": {
                    "platform": "linkedin",
                    "format": "Carousel",
                    "title": "5 ways AI agents cut ops cost",
                    "hook": "Most companies are using AI wrong...",
                    "caption": "Full caption...",
                    "cta": "Comment AI for the framework",
                    "key_points": ["Define the problem", "Show a framework", "Prove ROI"],
                    "slides": [
                        {
                            "slide_number": 1,
                            "headline": "AI Agents",
                            "body": "Cut ops cost",
                            "image_prompt": "Clean cover graphic about AI agents",
                        }
                    ],
                    "image_prompt": "Hero still about AI agents",
                    "script_brief": "Create a LinkedIn carousel about AI agents...",
                },
            }
        },
    )

    user_request: str = Field(
        default="",
        description=(
            "What to create. Optional when content_suggestion.script_brief is provided."
        ),
    )
    content_type: Literal["video", "image"] = Field(
        default="video",
        description="video = timed script/scenes; image = stills/carousel slides.",
    )
    duration_seconds: int = Field(default=30, ge=1, le=120)
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = "16:9"
    style: str = Field(default="cinematic")
    content_suggestion: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Optional calendar item / generation_payload.content_suggestion from "
            "the content recommendation agent."
        ),
    )

    @model_validator(mode="after")
    def _require_brief(self) -> "ScriptGenerationRequest":
        suggestion = self.content_suggestion or {}
        brief = (
            (self.user_request or "").strip()
            or str(suggestion.get("script_brief") or "").strip()
            or str(suggestion.get("title") or suggestion.get("topic") or "").strip()
        )
        if len(brief) < 8:
            raise ValueError(
                "Provide user_request or content_suggestion with script_brief/title "
                "(at least 8 characters)."
            )
        return self

    def to_agent_config(self) -> dict[str, Any]:
        suggestion = dict(self.content_suggestion or {})
        content_type = self.content_type
        if suggestion.get("media_type") in {"image", "video"}:
            content_type = str(suggestion["media_type"])
        elif suggestion.get("format"):
            fmt = str(suggestion.get("format") or "").lower()
            if any(token in fmt for token in ("reel", "video", "story", "short")):
                content_type = "video"
            elif any(token in fmt for token in ("carousel", "image", "static", "document")):
                content_type = "image"

        brief = (
            (self.user_request or "").strip()
            or str(suggestion.get("script_brief") or "").strip()
            or str(suggestion.get("title") or suggestion.get("topic") or "").strip()
        )
        if not brief:
            brief = "Create a short branded social content piece."

        aspect = self.aspect_ratio
        if suggestion.get("aspect_ratio") in {"16:9", "9:16", "1:1"}:
            aspect = suggestion["aspect_ratio"]

        duration = int(self.duration_seconds)
        if suggestion.get("duration_seconds"):
            try:
                duration = max(1, min(120, int(suggestion["duration_seconds"])))
            except (TypeError, ValueError):
                pass
        elif content_type == "image" and self.duration_seconds == 30:
            duration = 5

        style = (self.style or "").strip() or "cinematic"
        if suggestion.get("visual_style") or suggestion.get("visual_direction"):
            style = str(
                suggestion.get("visual_style")
                or suggestion.get("visual_direction")
                or style
            ).strip()

        return {
            "user_request": brief,
            "content_type": content_type,
            "duration_seconds": duration,
            "aspect_ratio": aspect,
            "style": style,
            "content_suggestion": suggestion,
        }
