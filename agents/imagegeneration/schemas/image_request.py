from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

Platform = Literal["instagram", "linkedin", "facebook", "tiktok", "x", "twitter"]
Purpose = Literal["story", "post", "carousel", "reel"]


_PURPOSE_ASPECT = {
    ("instagram", "story"): "9:16",
    ("instagram", "post"): "1:1",
    ("instagram", "carousel"): "1:1",
    ("instagram", "reel"): "9:16",
    ("linkedin", "story"): "9:16",
    ("linkedin", "post"): "1:1",
    ("linkedin", "carousel"): "1:1",
    ("linkedin", "reel"): "9:16",
    ("facebook", "story"): "9:16",
    ("facebook", "post"): "1:1",
    ("facebook", "carousel"): "1:1",
    ("facebook", "reel"): "9:16",
    ("tiktok", "story"): "9:16",
    ("tiktok", "post"): "9:16",
    ("tiktok", "carousel"): "9:16",
    ("tiktok", "reel"): "9:16",
    ("x", "post"): "16:9",
    ("x", "reel"): "9:16",
    ("twitter", "post"): "16:9",
    ("twitter", "reel"): "9:16",
}


class ImageGenerationRequest(BaseModel):
    """Generate stills from a script-generator result for a platform purpose."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "company_id": "550e8400-e29b-41d4-a716-446655440000",
                "platform": "instagram",
                "purpose": "carousel",
                "style": "clean modern social graphic",
                "project": {"name": "AI Agents carousel", "tone": "professional"},
                "script": {
                    "title": "5 ways AI agents cut ops cost",
                    "hook": "Most companies are using AI wrong",
                    "caption": "Practical AI tips for founders",
                    "cta": "Save this",
                },
                "scenes": [
                    {
                        "scene_number": 1,
                        "headline": "AI Agents",
                        "body_text": "Cut ops cost",
                        "visual_prompt": "Clean cover graphic about AI agents",
                        "action": "Title slide",
                    }
                ],
            }
        },
    )

    company_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("company_id", "companyId"),
        serialization_alias="company_id",
        description="External company identifier to link generated assets.",
        examples=["550e8400-e29b-41d4-a716-446655440000", "org_12345"],
    )
    platform: Platform = Field(..., description="Target social platform.")
    purpose: Purpose = Field(
        ...,
        description="Content format purpose: story, post, carousel, or reel.",
    )
    project: dict[str, Any] = Field(default_factory=dict)
    script: dict[str, Any] = Field(default_factory=dict)
    characters: list[dict[str, Any]] = Field(default_factory=list)
    scenes: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Scenes/slides from POST /script-generation/script",
    )
    style: str = Field(default="clean modern social graphic")
    aspect_ratio: Literal["1:1", "9:16", "16:9", "3:4", "4:3"] | None = Field(
        default=None,
        description="Optional override. Defaults from platform + purpose.",
    )
    max_images: int = Field(default=8, ge=1, le=12)
    generate_media: bool = Field(
        default=True,
        description="If false, only build prompts (no Gemini calls).",
    )
    return_base64: bool = Field(
        default=False,
        description="If true, also include image_base64 in the JSON response.",
    )
    upload_s3: bool = Field(
        default=True,
        description="Upload each still to AWS S3 and return url/s3_url (production default).",
    )
    save_local: bool = Field(
        default=False,
        description=(
            "Dev/testing only. If true, also write files under generated/images "
            "and return /media/images/... url."
        ),
    )
    include_data_url: bool = Field(
        default=False,
        description="Deprecated. Use return_base64 instead.",
    )

    @field_validator("company_id")
    @classmethod
    def _strip_company_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("purpose", mode="before")
    @classmethod
    def _normalize_purpose(cls, value: Any) -> str:
        text = str(value or "post").strip().lower()
        if text in {"reel", "reels", "short", "shorts", "motion", "video"}:
            return "reel"
        if text in {"story", "stories"}:
            return "story"
        if text in {"carousel", "carousels", "slides"}:
            return "carousel"
        if text in {"post", "feed", "image", "static"}:
            return "post"
        return text

    @model_validator(mode="after")
    def _require_visual_source(self) -> "ImageGenerationRequest":
        has_scenes = bool(self.scenes)
        script = self.script or {}
        has_script = bool(
            script.get("body")
            or script.get("title")
            or script.get("caption")
            or script.get("hook")
        )
        if not has_scenes and not has_script:
            raise ValueError("Provide scenes and/or script from the script generator.")
        return self

    def resolve_aspect_ratio(self) -> str:
        if self.aspect_ratio:
            return self.aspect_ratio
        platform = str(self.platform).lower()
        purpose = str(self.purpose).lower()
        return _PURPOSE_ASPECT.get((platform, purpose), "1:1")

    def resolve_scenes(self) -> list[dict[str, Any]]:
        from agents.imagegeneration.Node.PromptBuilder import _resolve_image_scenes

        return _resolve_image_scenes(
            scenes=[scene for scene in (self.scenes or []) if isinstance(scene, dict)],
            script=dict(self.script or {}),
            project=dict(self.project or {}),
            purpose=str(self.purpose).lower(),
            max_images=int(self.max_images),
        )

    def to_agent_config(self) -> dict[str, Any]:
        project = dict(self.project or {})
        company_id = (
            self.company_id
            or project.get("company_id")
            or project.get("id")
        )
        if company_id:
            project.setdefault("company_id", company_id)

        return {
            "company_id": company_id,
            "platform": str(self.platform).lower(),
            "purpose": str(self.purpose).lower(),
            "project": project,
            "script": dict(self.script or {}),
            "characters": list(self.characters or []),
            "scenes": self.resolve_scenes(),
            "style": (self.style or "").strip() or "clean modern social graphic",
            "aspect_ratio": self.resolve_aspect_ratio(),
            "max_images": int(self.max_images),
            "generate_media": bool(self.generate_media),
            "return_base64": bool(self.return_base64 or self.include_data_url),
            "upload_s3": bool(self.upload_s3),
            "save_local": bool(self.save_local),
        }
