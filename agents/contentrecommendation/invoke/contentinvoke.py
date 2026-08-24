from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from agents.contentrecommendation.graph.contentgraph import content_recommendation_app
from agents.contentrecommendation.pipeline_log import (
    log_event,
    log_pipeline_complete,
    log_pipeline_start,
)
from agents.contentrecommendation.schemas.content_request import ContentRecommendationRequest
from agents.contentrecommendation.state.contentstate import ContentState
from service.ContentRecommendation.builder import build_recommendation_payload


async def contentRecommendationAgent(request: ContentRecommendationRequest) -> dict[str, Any]:
    start = time.time()
    config = request.to_agent_config()

    log_pipeline_start(
        company=(config.get("company") or {}).get("name"),
        platforms=",".join(config.get("platforms") or []),
        calendar_days=config.get("calendar_days"),
    )

    initial_state: ContentState = {
        "config": config,
        "company": config.get("company") or {},
        "company_dna": config.get("company_dna") or {},
        "company_analysis": config.get("company_analysis") or {},
        "competitor_analysis": config.get("competitor_analysis") or {},
        "content_intelligence_input": config.get("content_intelligence") or {},
        "ninety_day_action_plan": config.get("ninety_day_action_plan") or {},
        "business_goals": config.get("business_goals") or [],
        "platforms": config.get("platforms") or ["linkedin", "instagram"],
        "calendar_days": int(config.get("calendar_days") or 90),
        "social_performance": {},
        "competitor_content": {},
        "content_opportunities": {},
        "content_strategy": {},
        "platform_strategy": {},
        "content_ideas": [],
        "content_calendar": {},
        "recommendation": {},
        "error": None,
        "logs": [],
    }

    try:
        final_state = await content_recommendation_app.ainvoke(initial_state)
    except Exception as exc:
        duration = round(time.time() - start, 3)
        log_pipeline_complete(status="failed", duration_sec=duration, error=str(exc)[:160])
        return {
            "success": False,
            "error": str(exc),
            "meta": {
                "duration_sec": duration,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_mode": "content_recommendation",
            },
        }

    duration = round(time.time() - start, 3)
    error = final_state.get("error")
    calendar = final_state.get("content_calendar") or {}
    ideas = final_state.get("content_ideas") or []
    recommendation = build_recommendation_payload(final_state)
    final_state["recommendation"] = recommendation

    has_output = bool(calendar.get("items") or ideas)
    # Recoverable LLM/network issues should not fail the whole response when
    # deterministic fallbacks already produced ideas/calendar.
    warning = None
    if has_output and error:
        warning = str(error)
        error = None
        success = True
        status = "partial"
    elif has_output:
        success = True
        status = "success"
    else:
        success = False
        status = "failed"

    log_pipeline_complete(
        status=status,
        duration_sec=duration,
        ideas=len(ideas),
        calendar_items=len(calendar.get("items") or []),
        error=(str(error or warning or "")[:120] or None),
    )
    log_event(
        "9_complete",
        "Result summary",
        success=success,
        ideas=len(ideas),
        calendar_items=len(calendar.get("items") or []),
    )

    return {
        "success": success,
        "error": error,
        "warning": warning,
        "social_performance": final_state.get("social_performance") or {},
        "competitor_content": final_state.get("competitor_content") or {},
        "content_opportunities": final_state.get("content_opportunities") or {},
        "content_strategy": final_state.get("content_strategy") or {},
        "platform_strategy": final_state.get("platform_strategy") or {},
        "content_ideas": ideas,
        "ninety_day_action_plan": final_state.get("ninety_day_action_plan") or {},
        "content_calendar": calendar,
        "recommendation": recommendation,
        "logs": final_state.get("logs") or [],
        "meta": {
            "duration_sec": duration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_mode": "content_recommendation",
            "platforms": config.get("platforms") or [],
            "calendar_days": config.get("calendar_days"),
            "idea_count": config.get("idea_count"),
            "status": status,
        },
    }
