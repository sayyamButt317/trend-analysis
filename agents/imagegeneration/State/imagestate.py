from __future__ import annotations

from typing import Any, TypedDict


class ImageState(TypedDict, total=False):
    platform: str
    purpose: str
    style: str
    aspect_ratio: str
    max_images: int
    generate_media: bool
    return_base64: bool
    save_local: bool
    project: dict[str, Any]
    script: dict[str, Any]
    characters: list[dict[str, Any]]
    scenes: list[dict[str, Any]]
    image_jobs: list[dict[str, Any]]
    generated_images: list[dict[str, Any]]
    error: str | None
    logs: list[str]
