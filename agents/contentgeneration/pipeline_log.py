from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger("contentgeneration.pipeline")

T = TypeVar("T")

PIPELINE_ORDER: list[tuple[str, str, str]] = [
    ("asset_manager", "2_production", "Prepare assets"),
    ("visual_prompt_generator", "2_production", "Write visual prompts"),
    ("higgsfield", "2_production", "Generate images via Higgsfield"),
    ("video_generator", "2_production", "Generate scene videos"),
    ("post_production", "3_post", "Quality check + final video"),
]

PIPELINE_STEPS: dict[str, tuple[str, str]] = {
    name: (phase, label) for name, phase, label in PIPELINE_ORDER
}
STEP_INDEX: dict[str, int] = {name: idx + 1 for idx, (name, _, _) in enumerate(PIPELINE_ORDER)}
TOTAL_STEPS = len(PIPELINE_ORDER)

PHASE_TITLES: dict[str, str] = {
    "0_request": "REQUEST",
    "2_production": "CONTENT AGENT — Assets, prompts, Higgsfield, video",
    "3_post": "POST PRODUCTION — Quality check + final video",
    "9_complete": "COMPLETE",
}

_last_phase_logged: str | None = None


def _format_details(**details: Any) -> str:
    if not details:
        return ""
    parts = [f"{key}={value}" for key, value in details.items() if value is not None]
    return (" | " + " ".join(parts)) if parts else ""


def log_event(phase: str, message: str, **details: Any) -> None:
    logger.info("[ContentGen %s] %s%s", phase, message, _format_details(**details))


def log_phase_banner(phase: str) -> None:
    global _last_phase_logged
    if phase == _last_phase_logged:
        return
    _last_phase_logged = phase
    title = PHASE_TITLES.get(phase, phase)
    logger.info("=" * 72)
    logger.info("[ContentGen] %s", title)
    logger.info("=" * 72)


def reset_pipeline_log_state() -> None:
    global _last_phase_logged
    _last_phase_logged = None


def log_pipeline_start(*, user_request: str = "", **details: Any) -> None:
    reset_pipeline_log_state()
    log_phase_banner("0_request")
    log_event(
        "0_request",
        "Content generation STARTED",
        preview=(user_request or "")[:80] or None,
        total_steps=TOTAL_STEPS,
        **details,
    )
    logger.info(
        "[ContentGen 0_request] Flow: assets → visual prompts → Higgsfield stills → video → post"
    )


def log_pipeline_complete(*, status: str, duration_sec: float, **details: Any) -> None:
    log_phase_banner("9_complete")
    log_event(
        "9_complete",
        f"Content generation FINISHED ({status})",
        duration_sec=round(duration_sec, 2),
        **details,
    )
    logger.info("=" * 72)


def log_step_start(node_name: str) -> tuple[str, str, float, int]:
    phase, label = PIPELINE_STEPS.get(node_name, ("?", node_name))
    step_no = STEP_INDEX.get(node_name, 0)
    started = time.perf_counter()
    log_phase_banner(phase)
    logger.info("-" * 72)
    log_event(
        phase,
        f"START [{step_no}/{TOTAL_STEPS}] → {label}",
        step=node_name,
    )
    return phase, label, started, step_no


def log_step_done(
    node_name: str,
    *,
    phase: str,
    label: str,
    started: float,
    state: dict[str, Any],
    step_no: int = 0,
) -> None:
    elapsed = time.perf_counter() - started
    details: dict[str, Any] = {
        "step": node_name,
        "elapsed_sec": round(elapsed, 2),
        "scenes": len(state.get("scenes") or []),
        "characters": len(state.get("characters") or []),
        "videos": len(state.get("generated_videos") or []),
    }
    error = state.get("error")
    if error:
        details["error"] = str(error)[:120]
    status = "DONE (with error)" if error else "DONE"
    index = step_no or STEP_INDEX.get(node_name, 0)
    log_event(phase, f"{status} [{index}/{TOTAL_STEPS}] → {label}", **details)
    logger.info("-" * 72)


def with_pipeline_log(
    node_name: str,
    fn: Callable[..., Awaitable[Any]],
) -> Callable[..., Awaitable[Any]]:
    async def wrapped(state: dict[str, Any]) -> dict[str, Any]:
        phase, label, started, step_no = log_step_start(node_name)
        try:
            result = await fn(state)
            log_step_done(
                node_name,
                phase=phase,
                label=label,
                started=started,
                state=result if isinstance(result, dict) else state,
                step_no=step_no,
            )
            return result
        except Exception:
            elapsed = time.perf_counter() - started
            logger.exception(
                "[ContentGen %s] FAILED [%s/%s] → %s | step=%s elapsed_sec=%.2f",
                phase,
                step_no,
                TOTAL_STEPS,
                label,
                node_name,
                elapsed,
            )
            raise

    wrapped.__name__ = getattr(fn, "__name__", node_name)
    wrapped.__qualname__ = getattr(fn, "__qualname__", node_name)
    return wrapped
