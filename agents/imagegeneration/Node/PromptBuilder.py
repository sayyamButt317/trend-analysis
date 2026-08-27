from __future__ import annotations

from typing import Any

from agents.imagegeneration.pipeline_log import log_event
from agents.imagegeneration.State.imagestate import ImageState


def _purpose_guidance(platform: str, purpose: str) -> str:
    if purpose == "story":
        return (
            f"Vertical {platform} story frame. Full-bleed, bold focal subject, "
            "safe margins for UI overlays, high contrast, mobile-first."
        )
    if purpose == "reel":
        return (
            f"Vertical {platform} reel still/cover. Full-bleed 9:16 composition, "
            "bold focal subject, high energy, mobile-first, safe margins for UI overlays."
        )
    if purpose == "carousel":
        return (
            f"{platform} carousel slide. Clear headline space, consistent series look, "
            "readable hierarchy, one idea per slide."
        )
    return (
        f"{platform} feed post. Strong single-image composition, brand-safe, "
        "works as a standalone social graphic."
    )


def _slides_to_scenes(slides: list[Any]) -> list[dict[str, Any]]:
    scenes: list[dict[str, Any]] = []
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            continue
        scenes.append(
            {
                "scene_number": slide.get("slide_number") or slide.get("scene_number") or index,
                "headline": slide.get("headline") or slide.get("title") or "",
                "body_text": slide.get("body_text") or slide.get("body") or slide.get("text") or "",
                "visual_prompt": slide.get("visual_prompt") or slide.get("image_prompt") or "",
                "action": slide.get("action") or slide.get("body") or "",
            }
        )
    return scenes


def _resolve_image_scenes(
    *,
    scenes: list[dict[str, Any]],
    script: dict[str, Any],
    project: dict[str, Any],
    purpose: str,
    max_images: int,
) -> list[dict[str, Any]]:
    """Prefer explicit scenes; for carousels expand from script/project slides when needed."""
    current = [scene for scene in scenes if isinstance(scene, dict)]
    slide_sources: list[Any] = []
    for source in (script, project):
        rows = source.get("slides") if isinstance(source.get("slides"), list) else []
        if rows:
            slide_sources = rows
            break

    if slide_sources:
        slide_scenes = _slides_to_scenes(slide_sources)
        if purpose == "carousel" and len(current) < len(slide_scenes):
            return slide_scenes[:max_images]
        if not current:
            return slide_scenes[:max_images]

    return current[:max_images]


def _scene_prompt(scene: dict, *, platform: str, purpose: str, style: str, script: dict) -> str:
    headline = str(scene.get("headline") or scene.get("title") or "").strip()
    body = str(scene.get("body_text") or scene.get("narration") or scene.get("action") or "").strip()
    visual = str(
        scene.get("visual_prompt")
        or scene.get("image_prompt")
        or ""
    ).strip()
    location = str(scene.get("location") or "").strip()
    camera = str(scene.get("camera") or "").strip()
    title = str(script.get("title") or "").strip()
    hook = str(script.get("hook") or "").strip()

    parts = [
        f"Create a social media still for {platform} {purpose}.",
        _purpose_guidance(platform, purpose),
        f"Visual style: {style}.",
    ]
    if title:
        parts.append(f"Content title: {title}.")
    if hook:
        parts.append(f"Hook: {hook}.")
    if headline:
        parts.append(f"Slide/headline: {headline}.")
    if body:
        parts.append(f"Copy intent: {body}.")
    if location:
        parts.append(f"Setting: {location}.")
    if camera:
        parts.append(f"Camera: {camera}.")
    if visual:
        parts.append(f"Visual direction: {visual}.")
    parts.append(
        "No watermarks, no UI chrome, no unreadable tiny text walls. "
        "Professional marketing quality."
    )
    return " ".join(parts)


def _build_jobs_from_scenes(
    scenes: list[dict[str, Any]],
    *,
    platform: str,
    purpose: str,
    style: str,
    script: dict[str, Any],
    project: dict[str, Any],
    aspect: str,
    max_images: int,
) -> list[dict[str, Any]]:
    selected = _resolve_image_scenes(
        scenes=scenes,
        script=script,
        project=project,
        purpose=purpose,
        max_images=max_images,
    )
    if purpose == "post" and len(selected) > 1:
        selected = selected[:1]
    if purpose in {"story", "reel"} and len(selected) > 3:
        selected = selected[:3]

    jobs: list[dict[str, Any]] = []
    for index, scene in enumerate(selected, start=1):
        if not isinstance(scene, dict):
            continue
        number = scene.get("scene_number") or index
        prompt = _scene_prompt(
            scene,
            platform=platform,
            purpose=purpose,
            style=style,
            script=script,
        )
        jobs.append(
            {
                "job_id": f"{platform}-{purpose}-{number}",
                "scene_number": number,
                "headline": scene.get("headline") or scene.get("title") or "",
                "purpose": purpose,
                "platform": platform,
                "aspect_ratio": aspect,
                "prompt": prompt,
            }
        )
    return jobs


async def PromptBuilderNode(state: ImageState) -> ImageState:
    logs = list(state.get("logs") or [])
    platform = (state.get("platform") or "instagram").lower()
    purpose = (state.get("purpose") or "post").lower()
    style = state.get("style") or "clean modern social graphic"
    aspect = state.get("aspect_ratio") or "1:1"
    max_images = int(state.get("max_images") or 8)
    script = state.get("script") or {}
    project = state.get("project") or {}
    scenes = list(state.get("scenes") or [])

    jobs = _build_jobs_from_scenes(
        scenes,
        platform=platform,
        purpose=purpose,
        style=style,
        script=script,
        project=project,
        aspect=aspect,
        max_images=max_images,
    )

    if not jobs:
        prompt = _scene_prompt(
            {
                "headline": script.get("title"),
                "body_text": script.get("caption") or script.get("body"),
                "visual_prompt": script.get("logline") or script.get("hook"),
            },
            platform=platform,
            purpose=purpose,
            style=style,
            script=script,
        )
        jobs.append(
            {
                "job_id": f"{platform}-{purpose}-1",
                "scene_number": 1,
                "headline": script.get("title") or "",
                "purpose": purpose,
                "platform": platform,
                "aspect_ratio": aspect,
                "prompt": prompt,
            }
        )

    resolved_scenes = _resolve_image_scenes(
        scenes=scenes,
        script=script,
        project=project,
        purpose=purpose,
        max_images=max_images,
    )
    if purpose == "carousel" and len(jobs) == 1 and len(resolved_scenes) > 1:
        logs.append("prompt_builder:carousel_single_slide_warning")

    logs.append(f"prompt_builder:{len(jobs)}:{platform}:{purpose}")
    log_event("1_prepare", "Image prompts ready", count=len(jobs), platform=platform, purpose=purpose)
    return {**state, "image_jobs": jobs, "logs": logs}
