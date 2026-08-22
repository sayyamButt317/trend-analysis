from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger("scriptgenerator.pipeline")

T = TypeVar("T")

PIPELINE_ORDER: list[tuple[str, str, str]] = [
    ("project_analyzer", "1_story", "Analyze project brief"),
    ("script_writer", "1_story", "Write script"),
    ("character_manager", "1_story", "Define characters"),
    ("scene_planner", "1_story", "Plan scenes"),
]

PIPELINE_STEPS: dict[str, tuple[str, str]] = {
    name: (phase, label) for name, phase, label in PIPELINE_ORDER
}
STEP_INDEX: dict[str, int] = {name: idx + 1 for idx, (name, _, _) in enumerate(PIPELINE_ORDER)}
TOTAL_STEPS = len(PIPELINE_ORDER)

PHASE_TITLES: dict[str, str] = {
    "0_request": "REQUEST",
    "1_story": "SCRIPT AGENT — Brief, script, characters, scenes",
    "9_complete": "COMPLETE",
}

_last_phase_logged: str | None = None


def _format_details(**details: Any) -> str:
    if not details:
        return ""
    parts = [f"{key}={value}" for key, value in details.items() if value is not None]
    return (" | " + " ".join(parts)) if parts else ""


def log_event(phase: str, message: str, **details: Any) -> None:
    logger.info("[ScriptGen %s] %s%s", phase, message, _format_details(**details))


def log_phase_banner(phase: str) -> None:
    global _last_phase_logged
    if phase == _last_phase_logged:
        return
    _last_phase_logged = phase
    title = PHASE_TITLES.get(phase, phase)
    logger.info("=" * 72)
    logger.info("[ScriptGen] %s", title)
    logger.info("=" * 72)


def reset_pipeline_log_state() -> None:
    global _last_phase_logged
    _last_phase_logged = None


def log_pipeline_start(*, user_request: str, **details: Any) -> None:
    reset_pipeline_log_state()
    log_phase_banner("0_request")
    log_event(
        "0_request",
        "Script generation STARTED",
        preview=(user_request or "")[:80],
        total_steps=TOTAL_STEPS,
        **details,
    )
    logger.info(
        "[ScriptGen 0_request] Flow: project brief → script → characters → scenes"
    )


def log_pipeline_complete(*, status: str, duration_sec: float, **details: Any) -> None:
    log_phase_banner("9_complete")
    log_event(
        "9_complete",
        f"Script generation FINISHED ({status})",
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
                "[ScriptGen %s] FAILED [%s/%s] → %s | step=%s elapsed_sec=%.2f",
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
