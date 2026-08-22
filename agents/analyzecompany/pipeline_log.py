from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger("analyzecompany.pipeline")

T = TypeVar("T")

PIPELINE_ORDER: list[tuple[str, str, str]] = [
    ("understand_company", "1_company", "Understand company & crawl website"),
    ("analyze_user_instagram", "1_company", "Analyze user Instagram"),
    ("analyze_user_linkedin", "1_company", "Analyze user LinkedIn"),
    ("generate_company_summary", "2_summary", "Generate reusable company summary"),
    ("digital_presence", "3_intelligence", "Score digital presence"),
    ("market_position", "3_intelligence", "Assess market position"),
    ("executive_snapshot", "3_intelligence", "Build executive snapshot"),
    ("strengths_weaknesses", "3_intelligence", "Derive strengths & weaknesses"),
    ("growth_opportunities", "3_intelligence", "Identify growth opportunities"),
    ("recommendations", "3_intelligence", "Build recommended action plan"),
]

PIPELINE_STEPS: dict[str, tuple[str, str]] = {
    name: (phase, label) for name, phase, label in PIPELINE_ORDER
}
STEP_INDEX: dict[str, int] = {name: idx + 1 for idx, (name, _, _) in enumerate(PIPELINE_ORDER)}
TOTAL_STEPS = len(PIPELINE_ORDER)

PHASE_TITLES: dict[str, str] = {
    "0_request": "REQUEST",
    "1_company": "PHASE 1 — Company DNA (website + Instagram + LinkedIn)",
    "2_summary": "PHASE 2 — Build reusable company summary",
    "3_intelligence": "PHASE 3 — Company intelligence & recommendations",
    "9_complete": "COMPLETE",
}

_last_phase_logged: str | None = None


def _format_details(**details: Any) -> str:
    if not details:
        return ""
    parts = [f"{key}={value}" for key, value in details.items() if value is not None]
    return (" | " + " ".join(parts)) if parts else ""


def log_event(phase: str, message: str, **details: Any) -> None:
    logger.info("[AnalyzeCompany %s] %s%s", phase, message, _format_details(**details))


def log_phase_banner(phase: str) -> None:
    global _last_phase_logged
    if phase == _last_phase_logged:
        return
    _last_phase_logged = phase
    title = PHASE_TITLES.get(phase, phase)
    logger.info("=" * 72)
    logger.info("[AnalyzeCompany] %s", title)
    logger.info("=" * 72)


def log_pipeline_start(**details: Any) -> None:
    global _last_phase_logged
    _last_phase_logged = None
    log_phase_banner("0_request")
    log_event("0_request", "Pipeline start", **details)


def log_pipeline_complete(**details: Any) -> None:
    log_phase_banner("9_complete")
    log_event("9_complete", "Pipeline complete", **details)


def with_pipeline_log(step_name: str, node_fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    phase, label = PIPELINE_STEPS.get(step_name, ("?", step_name))
    index = STEP_INDEX.get(step_name, 0)

    async def _wrapped(state: Any) -> T:
        log_phase_banner(phase)
        log_event(phase, f"START [{index}/{TOTAL_STEPS}] {label}", step=step_name)
        started = time.time()
        try:
            result = await node_fn(state)
            log_event(
                phase,
                f"DONE  [{index}/{TOTAL_STEPS}] {label}",
                step=step_name,
                duration_sec=round(time.time() - started, 2),
            )
            return result
        except Exception as exc:
            log_event(
                phase,
                f"FAIL  [{index}/{TOTAL_STEPS}] {label}",
                step=step_name,
                duration_sec=round(time.time() - started, 2),
                error=str(exc)[:160],
            )
            raise

    _wrapped.__name__ = getattr(node_fn, "__name__", step_name)
    return _wrapped
