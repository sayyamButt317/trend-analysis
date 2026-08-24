from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from agents.contentrecommendation.state.contentstate import ContentState
from service.Competitor.openai_client import (
    chat_completion_json,
    resolve_openai_model,
)

logger = logging.getLogger(__name__)

_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_DEFAULT_PLATFORMS = ("linkedin", "instagram")
_VIDEO_FORMATS = {
    "reel",
    "reels",
    "video",
    "short",
    "shorts",
    "story",
    "stories",
    "motion",
}


def _phase_for_offset(offset: int) -> str:
    if offset < 30:
        return "0-30 days"
    if offset < 60:
        return "31-60 days"
    return "61-90 days"


def _phase_actions(plan: dict[str, Any], phase: str) -> list[dict[str, Any]]:
    key_map = {
        "0-30 days": "days_0_30",
        "31-60 days": "days_31_60",
        "61-90 days": "days_61_90",
    }
    rows = plan.get(key_map.get(phase) or "") or []
    if isinstance(rows, list) and rows:
        return [row for row in rows if isinstance(row, dict)]
    all_actions = plan.get("all_actions") or []
    if isinstance(all_actions, list):
        return [
            row
            for row in all_actions
            if isinstance(row, dict)
            and str(row.get("timeline") or "").lower() == phase.lower()
        ]
    return []


def _title(value: Any) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return ""
    if text.lower() in {"ai", "ml", "ui", "ux", "b2b", "saas"}:
        return text.upper()
    return text[0].upper() + text[1:]


def _platform_label(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"li", "linkedin"}:
        return "LinkedIn"
    if raw in {"ig", "instagram", "insta"}:
        return "Instagram"
    return _title(raw) or "LinkedIn"


def _infer_media_type(fmt: str, platform: str) -> str:
    token = str(fmt or "").strip().lower()
    if any(part in token for part in _VIDEO_FORMATS):
        return "video"
    if "reel" in token or "video" in token:
        return "video"
    # Default stills/carousels/documents to image for the image/video pipeline.
    if platform == "instagram" and token in {"story", "stories"}:
        return "video"
    return "image"


def _aspect_for(platform: str, media_type: str, fmt: str) -> str:
    token = str(fmt or "").lower()
    if media_type == "video":
        return "9:16" if platform == "instagram" or "reel" in token else "16:9"
    if "carousel" in token or platform == "instagram":
        return "1:1"
    return "1:1" if platform == "instagram" else "16:9"


def _as_list(value: Any, *, limit: int = 8) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _build_slides(
    *,
    topic: str,
    key_points: list[str],
    fmt: str,
    visual_direction: str,
    raw_slides: Any,
) -> list[dict[str, Any]]:
    if isinstance(raw_slides, list) and raw_slides:
        slides: list[dict[str, Any]] = []
        for index, slide in enumerate(raw_slides[:8], start=1):
            if not isinstance(slide, dict):
                continue
            headline = str(slide.get("headline") or slide.get("title") or topic).strip()
            body = str(slide.get("body") or slide.get("text") or "").strip()
            prompt = str(
                slide.get("image_prompt")
                or slide.get("visual_prompt")
                or f"{visual_direction}. Slide {index}: {headline}. {body}".strip()
            ).strip()
            slides.append(
                {
                    "slide_number": index,
                    "headline": headline[:120],
                    "body": body[:280],
                    "image_prompt": prompt[:500],
                }
            )
        if slides:
            return slides

    points = key_points or [
        f"Why {topic} matters now",
        f"Practical takeaway on {topic}",
        f"Next step for teams adopting {topic}",
    ]
    if "carousel" not in str(fmt).lower() and len(points) <= 1:
        return [
            {
                "slide_number": 1,
                "headline": topic[:120],
                "body": points[0][:280],
                "image_prompt": f"{visual_direction}. Single post visual about {topic}.",
            }
        ]

    slides = [
        {
            "slide_number": 1,
            "headline": topic[:120],
            "body": f"A practical breakdown of {topic}",
            "image_prompt": f"{visual_direction}. Cover slide for {topic}. Bold title, clean layout.",
        }
    ]
    for index, point in enumerate(points[:5], start=2):
        slides.append(
            {
                "slide_number": index,
                "headline": point[:120],
                "body": point[:280],
                "image_prompt": (
                    f"{visual_direction}. Carousel slide {index} about {topic}: {point}"
                ),
            }
        )
    slides.append(
        {
            "slide_number": len(slides) + 1,
            "headline": "Take action",
            "body": f"Apply {topic} this week.",
            "image_prompt": f"{visual_direction}. Closing CTA slide for {topic}.",
        }
    )
    return slides


def _build_generation_payload(item: dict[str, Any]) -> dict[str, Any]:
    media_type = item.get("media_type") or "image"
    title = item.get("title") or item.get("topic") or "Content piece"
    brief = item.get("script_brief") or (
        f"{media_type.title()} {item.get('format') or 'post'} for "
        f"{_platform_label(item.get('platform'))} about {title}. "
        f"Hook: {item.get('hook') or ''}. Goal: {item.get('goal') or 'Authority'}."
    )
    return {
        "content_type": media_type,
        "user_request": brief,
        "duration_seconds": int(item.get("duration_seconds") or (30 if media_type == "video" else 5)),
        "aspect_ratio": item.get("aspect_ratio") or "1:1",
        "style": item.get("visual_style") or "clean professional social content",
        "content_suggestion": {
            "platform": item.get("platform"),
            "format": item.get("format"),
            "pillar": item.get("pillar"),
            "topic": item.get("topic"),
            "goal": item.get("goal"),
            "title": item.get("title"),
            "hook": item.get("hook"),
            "caption": item.get("caption"),
            "cta": item.get("cta"),
            "key_points": item.get("key_points") or [],
            "hashtags": item.get("hashtags") or [],
            "target_audience": item.get("target_audience"),
            "visual_direction": item.get("visual_direction"),
            "image_prompt": item.get("image_prompt"),
            "slides": item.get("slides") or [],
            "script_brief": item.get("script_brief"),
            "phase": item.get("phase"),
            "date": item.get("date"),
        },
    }


def _normalize_item(
    raw: dict[str, Any],
    *,
    offset: int,
    start: date,
    platforms: list[str],
    pillars: list[dict[str, Any]],
    ideas: list[dict[str, Any]],
    plan: dict[str, Any],
    company: dict[str, Any] | None = None,
) -> dict[str, Any]:
    day = start + timedelta(days=offset)
    phase = _phase_for_offset(offset)
    actions = _phase_actions(plan, phase)
    action = actions[offset % len(actions)] if actions else {}
    idea = ideas[offset % len(ideas)] if ideas else {}
    pillar_row = pillars[offset % len(pillars)] if pillars else {}
    company = company or {}

    platform = (
        raw.get("platform")
        or idea.get("platform")
        or (platforms[offset % len(platforms)] if platforms else "linkedin")
    )
    platform = str(platform).strip().lower()
    fmt = _title(
        raw.get("format")
        or idea.get("format")
        or ("Carousel" if offset % 2 == 0 else "Reel")
    )
    pillar = _title(
        raw.get("pillar")
        or raw.get("content_pillar")
        or idea.get("content_pillar")
        or pillar_row.get("name")
        or "Education"
    )
    action_topic = action.get("title") or action.get("action")
    idea_topic = idea.get("title") or idea.get("angle")
    if offset % 2 == 0:
        topic = raw.get("topic") or raw.get("title") or idea_topic or action_topic
    else:
        topic = raw.get("topic") or raw.get("title") or action_topic or idea_topic
    topic = str(topic or "Industry insight").strip()
    goal = _title(
        raw.get("goal")
        or raw.get("objective")
        or idea.get("objective")
        or pillar_row.get("objective")
        or action.get("category")
        or "Authority"
    )

    media_type = str(
        raw.get("media_type")
        or raw.get("content_type")
        or _infer_media_type(fmt, platform)
    ).strip().lower()
    if media_type not in {"image", "video"}:
        media_type = _infer_media_type(fmt, platform)

    title = str(raw.get("title") or idea.get("title") or topic).strip()
    hook = str(
        raw.get("hook")
        or idea.get("hook")
        or f"Most teams still get {topic} wrong."
    ).strip()
    key_points = _as_list(raw.get("key_points") or idea.get("key_points"), limit=6)
    if not key_points:
        key_points = [
            f"Define the problem around {topic}",
            f"Show a practical framework for {topic}",
            f"Connect {topic} to measurable business outcomes",
        ]
    cta = str(
        raw.get("cta")
        or idea.get("cta")
        or ("Comment for the framework." if platform == "linkedin" else "Save this for later.")
    ).strip()
    raw_audience = raw.get("target_audience") or idea.get("target_audience")
    company_audience = company.get("target_audience")
    if isinstance(company_audience, list) and company_audience:
        company_audience = company_audience[0]
    audience = str(raw_audience or company_audience or "decision makers").strip()
    caption = str(
        raw.get("caption")
        or (
            f"{hook}\n\n"
            + "\n".join(f"• {point}" for point in key_points[:4])
            + f"\n\n{cta}"
        )
    ).strip()
    hashtags = _as_list(raw.get("hashtags"), limit=8)
    if not hashtags:
        brand = str(company.get("name") or "Growth").replace(" ", "")
        hashtags = [f"#{brand}", f"#{''.join(ch for ch in topic.title() if ch.isalnum())[:24]}", "#B2B"]

    visual_style = str(
        raw.get("visual_style")
        or ("dynamic social video" if media_type == "video" else "clean modern social graphic")
    ).strip()
    visual_direction = str(
        raw.get("visual_direction")
        or (
            f"{visual_style} for {_platform_label(platform)}. "
            f"Subject: {topic}. Brand tone: professional, practical, high-contrast."
        )
    ).strip()
    image_prompt = str(
        raw.get("image_prompt")
        or raw.get("visual_prompt")
        or f"{visual_direction}. Hero visual about {title}. No cluttered text walls."
    ).strip()
    aspect_ratio = str(
        raw.get("aspect_ratio") or _aspect_for(platform, media_type, fmt)
    ).strip()
    duration_seconds = int(
        raw.get("duration_seconds")
        or (30 if media_type == "video" else 5)
    )
    slides = _build_slides(
        topic=title,
        key_points=key_points,
        fmt=fmt,
        visual_direction=visual_direction,
        raw_slides=raw.get("slides"),
    )
    script_brief = str(
        raw.get("script_brief")
        or (
            f"Create a {duration_seconds}s {platform} {fmt} about {title}. "
            f"Audience: {audience}. Hook: {hook}. Key points: {'; '.join(key_points)}. "
            f"CTA: {cta}. Visual direction: {visual_direction}."
            if media_type == "video"
            else (
                f"Create a {_platform_label(platform)} {fmt} image/carousel about {title}. "
                f"Audience: {audience}. Hook: {hook}. Caption intent: {goal}. "
                f"Slides/points: {'; '.join(key_points)}. CTA: {cta}. "
                f"Visual direction: {visual_direction}."
            )
        )
    ).strip()

    item = {
        "id": f"cal-{day.isoformat()}-{platform}-{offset}",
        "day": raw.get("day") or _DAYS[day.weekday()],
        "date": raw.get("date") or day.isoformat(),
        "platform": platform,
        "format": fmt,
        "pillar": pillar,
        "topic": topic,
        "goal": goal,
        "phase": raw.get("phase") or phase,
        "media_type": media_type,
        "title": title[:160],
        "hook": hook[:280],
        "caption": caption[:1200],
        "cta": cta[:200],
        "key_points": key_points,
        "target_audience": audience[:120],
        "hashtags": hashtags,
        "aspect_ratio": aspect_ratio,
        "duration_seconds": duration_seconds,
        "visual_style": visual_style[:80],
        "visual_direction": visual_direction[:400],
        "image_prompt": image_prompt[:500],
        "slides": slides,
        "script_brief": script_brief[:1000],
        "action_ref": action.get("title") or action.get("action"),
        "idea_ref": idea.get("title"),
        "reason": str(
            raw.get("reason")
            or idea.get("reason")
            or action.get("action")
            or f"Supports {phase} focus on {topic}"
        ).strip()[:400],
    }
    item["generation_payload"] = _build_generation_payload(item)
    return item


def _build_table(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "Day": item.get("day") or "",
            "Platform": _platform_label(item.get("platform")),
            "Format": _title(item.get("format")),
            "Pillar": _title(item.get("pillar")),
            "Topic": str(item.get("topic") or "").strip(),
            "Goal": _title(item.get("goal")),
            "Media": str(item.get("media_type") or "").title(),
        }
        for item in items
    ]


def _weekday_offsets(calendar_days: int, *, skip_weekends: bool) -> list[int]:
    if not skip_weekends:
        return list(range(calendar_days))
    offsets: list[int] = []
    for offset in range(calendar_days):
        if (date.today() + timedelta(days=offset)).weekday() < 5:
            offsets.append(offset)
    return offsets or list(range(min(calendar_days, 5)))


def _group_phases(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_phase: dict[str, list[dict[str, Any]]] = {
        "days_0_30": [],
        "days_31_60": [],
        "days_61_90": [],
    }
    for item in items:
        phase = str(item.get("phase") or _phase_for_offset(0))
        if phase.startswith("0"):
            by_phase["days_0_30"].append(item)
        elif phase.startswith("31"):
            by_phase["days_31_60"].append(item)
        else:
            by_phase["days_61_90"].append(item)
    return by_phase


def build_fallback_calendar(
    *,
    content_ideas: list[dict[str, Any]],
    content_strategy: dict[str, Any] | None,
    ninety_day_plan: dict[str, Any] | None,
    platforms: list[str] | None,
    calendar_days: int = 90,
    skip_weekends: bool = True,
    company: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan = ninety_day_plan or {}
    pillars = ((content_strategy or {}).get("strategy") or {}).get("content_pillars") or []
    requested = [p.lower() for p in (platforms or list(_DEFAULT_PLATFORMS)) if p]
    start = date.today()
    offsets = _weekday_offsets(calendar_days, skip_weekends=skip_weekends)

    items = [
        _normalize_item(
            {},
            offset=offset,
            start=start,
            platforms=requested,
            pillars=pillars if isinstance(pillars, list) else [],
            ideas=content_ideas or [],
            plan=plan,
            company=company,
        )
        for offset in offsets
    ]
    return {
        "days": calendar_days,
        "start_date": start.isoformat(),
        "skip_weekends": skip_weekends,
        "source_plan_summary": plan.get("summary"),
        "phases": _group_phases(items),
        "items": items,
        "table": _build_table(items),
        "generation_ready": [item.get("generation_payload") for item in items],
    }


def _build_calendar_input(data: dict[str, Any]) -> dict[str, Any]:
    plan = (
        data.get("ninety_day_action_plan")
        or data.get("90_day_action_plan")
        or {}
    )
    if not isinstance(plan, dict):
        plan = {}
    return {
        "company": data.get("company") or {},
        "company_dna": data.get("company_dna") or {},
        "business_goals": data.get("business_goals") or [],
        "platforms": data.get("platforms") or list(_DEFAULT_PLATFORMS),
        "calendar_days": int(data.get("calendar_days") or 90),
        "content_strategy": data.get("content_strategy") or {},
        "platform_strategy": data.get("platform_strategy") or {},
        "content_ideas": data.get("content_ideas") or [],
        "content_opportunities": data.get("content_opportunities") or {},
        "ninety_day_action_plan": plan,
    }


def _build_prompt(analysis_input: dict[str, Any]) -> str:
    calendar_days = analysis_input["calendar_days"]
    return f"""
You are a senior content operations strategist.

Turn the 90-day action plan into a DETAILED content calendar that a downstream
image/video generation agent can execute without guessing.

==================================================
COMPANY
==================================================

{analysis_input["company"]}

==================================================
COMPANY DNA
==================================================

{analysis_input["company_dna"]}

==================================================
BUSINESS GOALS
==================================================

{analysis_input["business_goals"]}

==================================================
90-DAY ACTION PLAN (SOURCE OF TRUTH)
==================================================

{analysis_input["ninety_day_action_plan"]}

==================================================
CONTENT STRATEGY
==================================================

{analysis_input["content_strategy"]}

==================================================
PLATFORM STRATEGY
==================================================

{analysis_input["platform_strategy"]}

==================================================
CONTENT IDEAS
==================================================

{analysis_input["content_ideas"]}

==================================================
CONTENT OPPORTUNITIES
==================================================

{analysis_input["content_opportunities"]}

==================================================
PLATFORMS
==================================================

{analysis_input["platforms"]}

==================================================
RULES
==================================================

1. Build a posting calendar for the next {calendar_days} calendar days.
2. Prefer weekdays (Mon-Fri).
3. Map each item to the matching 90-day phase (0-30 / 31-60 / 61-90).
4. Every item must be production-ready for image OR video generation.
5. Set media_type:
   - "video" for Reel / Video / Story motion
   - "image" for Carousel / static post / document / case-study graphic
6. Include hook, caption, cta, key_points, visual_direction, image_prompt.
7. For image/carousel formats include slides with headline, body, image_prompt.
8. For video formats include script_brief and duration_seconds.
9. Formats must fit the platform.
10. Do not invent company facts not present in the input.

==================================================
OUTPUT
==================================================

Return ONLY valid JSON:

{{
  "items": [
    {{
      "day": "Mon",
      "date": "YYYY-MM-DD",
      "platform": "linkedin",
      "format": "Carousel",
      "pillar": "AI Education",
      "topic": "AI Agents",
      "goal": "Authority",
      "phase": "0-30 days",
      "media_type": "image",
      "title": "5 ways AI agents cut ops cost",
      "hook": "Most companies are using AI wrong...",
      "caption": "full post caption",
      "cta": "Comment AI for the framework",
      "key_points": ["point 1", "point 2", "point 3"],
      "target_audience": "SME founders",
      "hashtags": ["#AI", "#B2B"],
      "aspect_ratio": "1:1",
      "duration_seconds": 5,
      "visual_style": "clean modern social graphic",
      "visual_direction": "flat illustration, high contrast, brand-safe",
      "image_prompt": "detailed still prompt",
      "slides": [
        {{
          "slide_number": 1,
          "headline": "AI Agents",
          "body": "cover copy",
          "image_prompt": "cover visual prompt"
        }}
      ],
      "script_brief": "brief the next script/image agent can consume",
      "reason": "why this post exists now"
    }}
  ]
}}
"""


async def generate_content_calendar(data: dict[str, Any]) -> dict[str, Any]:
    """Build a detailed content calendar for downstream image/video generation."""
    analysis_input = _build_calendar_input(data)
    calendar_days = max(3, min(int(analysis_input["calendar_days"]), 90))
    analysis_input["calendar_days"] = calendar_days
    company = analysis_input.get("company") or {}

    platforms = [
        str(p).strip().lower()
        for p in (analysis_input.get("platforms") or list(_DEFAULT_PLATFORMS))
        if str(p).strip()
    ] or list(_DEFAULT_PLATFORMS)

    fallback = build_fallback_calendar(
        content_ideas=list(analysis_input.get("content_ideas") or []),
        content_strategy=analysis_input.get("content_strategy") or {},
        ninety_day_plan=analysis_input.get("ninety_day_action_plan") or {},
        platforms=platforms,
        calendar_days=calendar_days,
        skip_weekends=True,
        company=company,
    )

    try:
        response = await chat_completion_json(
            model=resolve_openai_model(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a content calendar planner for an image/video production pipeline. "
                        "Every calendar item must include production details a script generator "
                        "can turn into image slides or a video script. Return JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": _build_prompt(analysis_input),
                },
            ],
            temperature=0.35,
            timeout=180,
        )
        raw_items = response.get("items") if isinstance(response, dict) else None
        if not isinstance(raw_items, list) or not raw_items:
            return fallback

        start = date.today()
        pillars = (
            ((analysis_input.get("content_strategy") or {}).get("strategy") or {}).get(
                "content_pillars"
            )
            or []
        )
        ideas = list(analysis_input.get("content_ideas") or [])
        plan = analysis_input.get("ninety_day_action_plan") or {}

        items: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_items):
            if not isinstance(raw, dict):
                continue
            offset = index
            if raw.get("date"):
                try:
                    offset = max(0, (date.fromisoformat(str(raw["date"])) - start).days)
                except ValueError:
                    offset = index
            items.append(
                _normalize_item(
                    raw,
                    offset=min(offset, calendar_days - 1),
                    start=start,
                    platforms=platforms,
                    pillars=pillars if isinstance(pillars, list) else [],
                    ideas=ideas,
                    plan=plan,
                    company=company,
                )
            )

        if not items:
            return fallback

        return {
            "days": calendar_days,
            "start_date": start.isoformat(),
            "skip_weekends": True,
            "source_plan_summary": plan.get("summary"),
            "phases": _group_phases(items),
            "items": items,
            "table": _build_table(items),
            "generation_ready": [item.get("generation_payload") for item in items],
        }
    except Exception:
        logger.exception("LLM content calendar generation failed; using fallback")
        return fallback


async def GenerateContentCalendarNode(state: ContentState) -> ContentState:
    try:
        config = state.get("config") or {}
        ninety_day_plan = (
            state.get("ninety_day_action_plan")
            or config.get("ninety_day_action_plan")
            or config.get("90_day_action_plan")
            or {}
        )
        if not isinstance(ninety_day_plan, dict):
            ninety_day_plan = {}

        data = {
            "company": state.get("company") or config.get("company") or {},
            "company_dna": state.get("company_dna") or config.get("company_dna") or {},
            "business_goals": (
                state.get("business_goals")
                or config.get("business_goals")
                or []
            ),
            "platforms": state.get("platforms") or config.get("platforms") or list(_DEFAULT_PLATFORMS),
            "calendar_days": (
                config.get("calendar_days")
                or state.get("calendar_days")
                or 90
            ),
            "content_strategy": state.get("content_strategy") or {},
            "platform_strategy": state.get("platform_strategy") or {},
            "content_ideas": state.get("content_ideas") or [],
            "content_opportunities": state.get("content_opportunities") or {},
            "ninety_day_action_plan": ninety_day_plan,
        }

        state["ninety_day_action_plan"] = ninety_day_plan
        state["content_calendar"] = await generate_content_calendar(data)
        state.setdefault("logs", []).append(
            "Detailed content calendar generated for image/video production handoff."
        )
        return state
    except Exception as exc:
        logger.exception("Content calendar generation failed")
        state["error"] = f"Content calendar generation failed: {exc}"
        return state
