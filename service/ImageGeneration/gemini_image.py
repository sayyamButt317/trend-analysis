from __future__ import annotations

import base64
import logging
import re
import time
from pathlib import Path
from typing import Any

import httpx

from config.credential_config import config

logger = logging.getLogger(__name__)

_GENERATED_DIR = Path(__file__).resolve().parents[2] / "generated" / "images"
_PUBLIC_PREFIX = "/media/images"
_ASPECT_MAP = {
    "1:1": "1:1",
    "9:16": "9:16",
    "16:9": "16:9",
    "3:4": "3:4",
    "4:3": "4:3",
}


def generated_images_dir() -> Path:
    _GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    return _GENERATED_DIR


def public_image_url(filename: str) -> str:
    return f"{_PUBLIC_PREFIX}/{filename}"


def resolve_gemini_image_model(model: str | None = None) -> str:
    value = (model or config.GEMINI_IMAGE_MODEL or "gemini-2.5-flash-image").strip()
    if value and "image" not in value.lower():
        logger.warning(
            "GEMINI_IMAGE_MODEL '%s' is not an image model; using gemini-2.5-flash-image",
            value,
        )
        return "gemini-2.5-flash-image"
    return value or "gemini-2.5-flash-image"


def gemini_image_configured() -> bool:
    return bool((config.GEMINI_API_KEY or "").strip())


def _safe_filename(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9._-]+", "_", (value or "image").strip())[:80]
    return text or "image"


async def generate_image_bytes(
    prompt: str,
    *,
    aspect_ratio: str = "1:1",
    model: str | None = None,
    timeout: float = 180,
) -> dict[str, Any]:
    """
    Generate one still via Gemini generateContent.
    Returns {mime_type, data_b64, bytes} or raises on failure.
    """
    api_key = (config.GEMINI_API_KEY or "").strip().strip('"').strip("'")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured")

    image_model = resolve_gemini_image_model(model)
    ratio = _ASPECT_MAP.get(str(aspect_ratio).strip(), "1:1")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{image_model}:generateContent"
    )
    payload: dict[str, Any] = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": ratio},
        },
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            url,
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json=payload,
        )

    if response.status_code != 200:
        detail = response.text[:500]
        raise RuntimeError(
            f"Gemini image generation failed ({response.status_code}): {detail}"
        )

    body = response.json()
    candidates = body.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            inline = part.get("inlineData") or part.get("inline_data") or {}
            data_b64 = inline.get("data")
            mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
            if data_b64:
                return {
                    "mime_type": mime,
                    "data_b64": data_b64,
                    "bytes": base64.b64decode(data_b64),
                    "model": image_model,
                    "aspect_ratio": ratio,
                }

    raise RuntimeError("Gemini returned no image data")


async def generate_image_asset(
    prompt: str,
    *,
    aspect_ratio: str = "1:1",
    filename_stem: str = "image",
    model: str | None = None,
    return_base64: bool = True,
    save_local: bool = False,
) -> dict[str, Any]:
    """
    Generate an image and package it for API response.

    Production default: return_base64=True, save_local=False
    (image bytes travel in the JSON response — no server disk required).
    """
    result = await generate_image_bytes(
        prompt,
        aspect_ratio=aspect_ratio,
        model=model,
    )
    mime = str(result["mime_type"])
    ext = "png" if "png" in mime else "jpg" if "jpeg" in mime or "jpg" in mime else "webp"
    stamp = int(time.time())
    filename = f"{_safe_filename(filename_stem)}_{stamp}.{ext}"

    payload: dict[str, Any] = {
        "filename": filename,
        "mime_type": mime,
        "model": result["model"],
        "aspect_ratio": result["aspect_ratio"],
        "bytes": len(result["bytes"]),
    }

    if return_base64:
        # Frontend: `data:${mime_type};base64,${image_base64}`
        payload["image_base64"] = result["data_b64"]

    if save_local:
        out_dir = generated_images_dir()
        path = out_dir / filename
        path.write_bytes(result["bytes"])
        payload["path"] = str(path)
        payload["url"] = public_image_url(filename)

    return payload


# Back-compat alias used by older call sites.
async def generate_and_save_image(
    prompt: str,
    *,
    aspect_ratio: str = "1:1",
    filename_stem: str = "image",
    model: str | None = None,
    include_data_url: bool = False,
    return_base64: bool = True,
    save_local: bool = False,
) -> dict[str, Any]:
    asset = await generate_image_asset(
        prompt,
        aspect_ratio=aspect_ratio,
        filename_stem=filename_stem,
        model=model,
        return_base64=return_base64 or include_data_url,
        save_local=save_local,
    )
    if include_data_url and asset.get("image_base64"):
        asset["data_url"] = f"data:{asset['mime_type']};base64,{asset['image_base64']}"
    return asset
