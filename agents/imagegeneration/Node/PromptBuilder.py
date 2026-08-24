from __future__ import annotations

from agents.imagegeneration.pipeline_log import log_event
from agents.imagegeneration.State.imagestate import ImageState


def _purpose_guidance(platform: str, purpose: str) -> str:
    if purpose == "story":
        return (
            f"Vertical {platform} story frame. Full-bleed, bold focal subject, "
            "safe margins for UI overlays, high contrast, mobile-first."
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


async def PromptBuilderNode(state: ImageState) -> ImageState:
    logs = list(state.get("logs") or [])
    platform = (state.get("platform") or "instagram").lower()
    purpose = (state.get("purpose") or "post").lower()
    style = state.get("style") or "clean modern social graphic"
    aspect = state.get("aspect_ratio") or "1:1"
    max_images = int(state.get("max_images") or 8)
    script = state.get("script") or {}
    scenes = list(state.get("scenes") or [])

    jobs: list[dict] = []
    if scenes:
        selected = scenes[:max_images]
        if purpose == "post" and len(selected) > 1:
            selected = selected[:1]
        if purpose == "story" and len(selected) > 3:
            selected = selected[:3]
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
    else:
        # Fallback: one image from script fields.
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

    logs.append(f"prompt_builder:{len(jobs)}:{platform}:{purpose}")
    log_event("1_prepare", "Image prompts ready", count=len(jobs), platform=platform, purpose=purpose)
    return {**state, "image_jobs": jobs, "logs": logs}
