from __future__ import annotations
import logging
import os
from typing import Any
from config.credential_config import config, higgsfield_api_key

logger = logging.getLogger(__name__)

IMAGE_MODEL = config.HIGGSFIELD_IMAGE_MODEL
VIDEO_MODEL = config.HIGGSFIELD_VIDEO_MODEL
IMAGE_FALLBACK_MODEL = "higgsfield-ai/soul/standard"

_configured = False
_import_error: str | None = None
_async_client: Any | None = None
_last_error: str | None = None
_disabled_models: set[str] = set()
_credits_exhausted = False


def higgsfield_keys_present() -> bool:
    return bool(higgsfield_api_key())


def higgsfield_import_error() -> str | None:
    _configure_client()
    return _import_error


def higgsfield_last_error() -> str | None:
    return _last_error


def higgsfield_configured() -> bool:
    return higgsfield_keys_present() and _configure_client() is not None


def _set_last_error(message: str | None) -> None:
    global _last_error
    _last_error = (message or "").strip() or None


def _configure_client() -> Any | None:
    global _configured, _import_error, _async_client
    if not higgsfield_keys_present():
        logger.warning("Higgsfield keys missing — skipping media generation")
        return None
    try:
        import higgsfield_client
    except ImportError as exc:
        _import_error = (
            "higgsfield-client is not installed. Run: pip install higgsfield-client"
        )
        logger.warning("%s (%s)", _import_error, exc)
        return None
    _import_error = None
    if not _configured:
        credential = higgsfield_api_key()
        key_id = (config.HIGGSFIELD_API_KEY_ID or "").strip()
        secret = (config.HIGGSFIELD_API_KEY_SECRET or "").strip()
        if ":" in credential and (not key_id or not secret):
            key_id, _, secret = credential.partition(":")

        os.environ["HIGGSFIELD_API_KEY"] = credential
        if key_id:
            os.environ["HIGGSFIELD_API_KEY_ID"] = key_id
        if secret:
            os.environ["HIGGSFIELD_API_KEY_SECRET"] = secret
        setter = getattr(higgsfield_client, "set_api_key", None)
        if callable(setter):
            setter(key_id, secret)
        _async_client = higgsfield_client.AsyncClient(api_key=credential)
        _configured = True
    return higgsfield_client


def _as_http_url(value: Any) -> str | None:
    if isinstance(value, str) and value.startswith("http"):
        return value
    if isinstance(value, dict):
        for key in ("url", "image_url", "video_url"):
            nested = value.get(key)
            if isinstance(nested, str) and nested.startswith("http"):
                return nested
    return None


def _first_url(payload: Any, keys: tuple[str, ...] = ("images", "videos", "clips")) -> str | None:
    if payload is None:
        return None
    direct = _as_http_url(payload)
    if direct:
        return direct
    if not isinstance(payload, dict):
        return None

    status = str(payload.get("status") or "").lower()
    if status in {"failed", "nsfw", "canceled"}:
        logger.warning("Higgsfield request %s: %s", status, payload.get("error") or payload)
        return None

    for key in keys:
        items = payload.get(key)
        url = _as_http_url(items)
        if url:
            return url
        if isinstance(items, list):
            for item in items:
                url = _as_http_url(item)
                if url:
                    return url
                if isinstance(item, dict):
                    url = _as_http_url(item.get("video") or item.get("image"))
                    if url:
                        return url

    for key in ("url", "video_url", "image_url", "video", "image", "output"):
        url = _as_http_url(payload.get(key))
        if url:
            return url

    jobs = payload.get("jobs")
    if isinstance(jobs, list):
        for job in jobs:
            if not isinstance(job, dict):
                continue
            results = job.get("results") or job.get("result") or {}
            url = _first_url(results, keys)
            if url:
                return url
    return None


def _image_arguments(model: str, prompt: str, aspect_ratio: str, resolution: str) -> dict[str, Any]:
    if "seedream" in model:
        return {
            "prompt": prompt,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "camera_fixed": False,
        }
    return {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "resolution": "720p",
    }


def _exception_text(exc: BaseException) -> str:
    return str(exc).lower()


def _is_credits_error(exc: BaseException) -> bool:
    text = _exception_text(exc)
    return "not_enough_credits" in text or "insufficient credit" in text


def _is_missing_model(exc: BaseException) -> bool:
    text = _exception_text(exc)
    return "model_not_found" in text or "not found" in text or "404" in text


def _payload_error(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()
    status = payload.get("status")
    if status and str(status).lower() != "completed":
        return f"Higgsfield status={status}"
    return None


async def generate_image(
    prompt: str,
    *,
    aspect_ratio: str = "16:9",
    resolution: str = "2K",
) -> str | None:
    global _credits_exhausted
    client = _configure_client()
    if not client or _async_client is None or not (prompt or "").strip():
        return None
    if _credits_exhausted:
        return None

    models: list[str] = [IMAGE_MODEL]
    if IMAGE_FALLBACK_MODEL not in models:
        models.append(IMAGE_FALLBACK_MODEL)

    text = prompt.strip()
    for model in models:
        if model in _disabled_models:
            continue
        arguments = _image_arguments(model, text, aspect_ratio, resolution)
        try:
            result = await _async_client.subscribe(model, arguments=arguments)
            url = _first_url(result, ("images", "videos"))
            if url:
                _set_last_error(None)
                return url
            message = _payload_error(result) or f"Higgsfield image result had no URL from {model}"
            _set_last_error(message)
            logger.warning("%s: %s", message, str(result)[:240])
        except Exception as exc:
            if _is_credits_error(exc):
                _credits_exhausted = True
                _set_last_error(
                    "Higgsfield account has no credits. Add credits at "
                    "https://cloud.higgsfield.ai then retry."
                )
                logger.error("Higgsfield credits exhausted (%s)", model)
                return None
            _set_last_error(f"{model}: {exc}")
            logger.exception("Higgsfield image generation failed (%s)", model)
            if _is_missing_model(exc) or "422" in _exception_text(exc) or "unprocessable" in _exception_text(exc):
                _disabled_models.add(model)
    return None


async def generate_video(
    prompt: str,
    *,
    image_url: str | None = None,
    aspect_ratio: str = "16:9",
) -> str | None:
    client = _configure_client()
    if not client or _async_client is None or not (prompt or "").strip():
        return None
    if not (image_url or "").strip():
        message = (
            f"{VIDEO_MODEL} requires image_url. Generate stills before image-to-video."
        )
        _set_last_error(message)
        logger.warning(message)
        return None

    arguments: dict[str, Any] = {
        "prompt": prompt.strip(),
        "image_url": image_url.strip(),
    }
    if "dop" not in VIDEO_MODEL:
        arguments["aspect_ratio"] = aspect_ratio
    try:
        result = await _async_client.subscribe(VIDEO_MODEL, arguments=arguments)
        url = _first_url(result, ("videos", "clips", "images"))
        if url:
            _set_last_error(None)
            return url
        message = _payload_error(result) or "Higgsfield video result had no URL"
        _set_last_error(message)
        logger.warning("%s: %s", message, str(result)[:240])
        return None
    except Exception as exc:
        _set_last_error(str(exc))
        logger.exception("Higgsfield video generation failed")
        return None
