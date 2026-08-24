from __future__ import annotations

from agents.imagegeneration.pipeline_log import log_event
from agents.imagegeneration.State.imagestate import ImageState
from service.ImageGeneration.gemini_image import (
    gemini_image_configured,
    generate_image_asset,
)


async def GeminiImageGeneratorNode(state: ImageState) -> ImageState:
    logs = list(state.get("logs") or [])
    jobs = list(state.get("image_jobs") or [])
    generate_media = bool(state.get("generate_media", True))
    # Production default: send base64 in API response, do not write disk.
    return_base64 = bool(state.get("return_base64", True))
    save_local = bool(state.get("save_local", False))
    images: list[dict] = []

    if not generate_media:
        logs.append("gemini:skipped_generate_media=false")
        log_event("2_generate", "Gemini skipped", reason="generate_media=false")
        return {**state, "generated_images": images, "logs": logs}

    if not jobs:
        message = "No image jobs to generate."
        logs.append("gemini:no_jobs")
        return {**state, "generated_images": images, "logs": logs, "error": message}

    if not gemini_image_configured():
        message = "GEMINI_API_KEY is not configured."
        logs.append("gemini:skipped_no_credentials")
        log_event("2_generate", "Gemini skipped", reason="no_credentials")
        return {**state, "generated_images": images, "logs": logs, "error": message}

    errors: list[str] = []
    for job in jobs:
        prompt = str(job.get("prompt") or "").strip()
        if not prompt:
            continue
        stem = str(job.get("job_id") or f"scene_{job.get('scene_number') or 1}")
        try:
            log_event(
                "2_generate",
                "Generating still",
                scene=job.get("scene_number"),
                platform=job.get("platform"),
                purpose=job.get("purpose"),
            )
            saved = await generate_image_asset(
                prompt,
                aspect_ratio=str(job.get("aspect_ratio") or state.get("aspect_ratio") or "1:1"),
                filename_stem=stem,
                return_base64=return_base64,
                save_local=save_local,
            )
            row = {
                "job_id": job.get("job_id"),
                "scene_number": job.get("scene_number"),
                "platform": job.get("platform"),
                "purpose": job.get("purpose"),
                "headline": job.get("headline"),
                "prompt": prompt[:300],
                "filename": saved.get("filename"),
                "mime_type": saved["mime_type"],
                "bytes": saved.get("bytes"),
                "model": saved["model"],
                "aspect_ratio": saved["aspect_ratio"],
            }
            if return_base64 and saved.get("image_base64"):
                row["image_base64"] = saved["image_base64"]
            if save_local:
                if saved.get("path"):
                    row["path"] = saved["path"]
                if saved.get("url"):
                    row["url"] = saved["url"]
            images.append(row)
            logs.append(f"gemini:ok:{stem}")
        except Exception as exc:
            errors.append(f"scene {job.get('scene_number')}: {exc}")
            logs.append(f"gemini:fail:{stem}:{exc}")
            log_event(
                "2_generate",
                "Still failed",
                scene=job.get("scene_number"),
                error=str(exc)[:120],
            )

    error = None
    if not images:
        error = "; ".join(errors) or "Gemini generated no images."
    elif errors:
        error = f"Partial failures: {'; '.join(errors[:3])}"

    log_event("2_generate", "Gemini stills done", count=len(images), failed=len(errors))
    return {
        **state,
        "generated_images": images,
        "logs": logs,
        "error": error,
    }
