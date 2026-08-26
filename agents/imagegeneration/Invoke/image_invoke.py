from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from agents.imagegeneration.Graph.image_graph import image_generation_app
from agents.imagegeneration.pipeline_log import (
    log_event,
    log_pipeline_complete,
    log_pipeline_start,
)
from agents.imagegeneration.schemas.image_request import ImageGenerationRequest
from agents.imagegeneration.State.imagestate import ImageState
from db.images_storage import save_image_generation_run


async def imageGenerationAgent(request: ImageGenerationRequest) -> dict[str, Any]:
    start = time.time()
    config = request.to_agent_config()

    log_pipeline_start(
        company_id=config.get("company_id"),
        platform=config["platform"],
        purpose=config["purpose"],
        aspect_ratio=config["aspect_ratio"],
        scenes=len(config.get("scenes") or []),
        generate_media=config["generate_media"],
    )

    initial_state: ImageState = {
        "company_id": config.get("company_id"),
        "platform": config["platform"],
        "purpose": config["purpose"],
        "style": config["style"],
        "aspect_ratio": config["aspect_ratio"],
        "max_images": config["max_images"],
        "generate_media": config["generate_media"],
        "return_base64": config.get("return_base64", False),
        "upload_s3": config.get("upload_s3", True),
        "save_local": config.get("save_local", False),
        "project": config.get("project") or {},
        "script": config.get("script") or {},
        "characters": config.get("characters") or [],
        "scenes": config.get("scenes") or [],
        "image_jobs": [],
        "generated_images": [],
        "error": None,
        "logs": [],
    }

    try:
        final_state = await image_generation_app.ainvoke(initial_state)
    except Exception as exc:
        duration = round(time.time() - start, 3)
        log_pipeline_complete(status="failed", duration_sec=duration, error=str(exc)[:160])
        return {
            "success": False,
            "error": str(exc),
            "meta": {
                "duration_sec": duration,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_mode": "image_generation",
                "company_id": config.get("company_id"),
                "platform": config["platform"],
                "purpose": config["purpose"],
            },
        }

    duration = round(time.time() - start, 3)
    error = final_state.get("error")
    images = final_state.get("generated_images") or []
    jobs = final_state.get("image_jobs") or []

    if config.get("generate_media"):
        success = bool(images) and (error is None or str(error).startswith("Partial"))
        status = "success" if success and not error else ("partial" if images else "failed")
    else:
        success = bool(jobs) and not error
        status = "success" if success else "failed"

    log_pipeline_complete(
        status=status,
        duration_sec=duration,
        images=len(images),
        jobs=len(jobs),
        error=(str(error)[:120] if error else None),
    )
    log_event("9_complete", "Result summary", success=success, images=len(images))

    response = {
        "success": success,
        "error": error,
        "company_id": config.get("company_id") or final_state.get("company_id"),
        "platform": config["platform"],
        "purpose": config["purpose"],
        "aspect_ratio": config["aspect_ratio"],
        "project": final_state.get("project") or {},
        "script": final_state.get("script") or {},
        "image_jobs": jobs,
        "generated_images": images,
        "logs": final_state.get("logs") or [],
        "meta": {
            "duration_sec": duration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_mode": "image_generation",
            "company_id": config.get("company_id"),
            "platform": config["platform"],
            "purpose": config["purpose"],
            "aspect_ratio": config["aspect_ratio"],
            "style": config["style"],
            "status": status,
            "images_count": len(images),
            "jobs_count": len(jobs),
        },
    }

    if config["purpose"] == "carousel" and len(images) == 1:
        response["meta"]["warning"] = (
            "Carousel generated 1 slide. Pass all scenes from POST /script-generation/script "
            "(or include script.slides / project.slides) for a multi-slide carousel."
        )

    storage_ids = await save_image_generation_run(request, response, duration_sec=duration)
    response["meta"]["prompt_id"] = storage_ids.get("prompt_id")
    response["meta"]["images_id"] = storage_ids.get("images_id")
    if storage_ids.get("storage_error"):
        response["meta"]["storage_error"] = storage_ids["storage_error"]
    return response
