from __future__ import annotations  
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

logger = logging.getLogger("competitor.pipeline")

T = TypeVar("T")

PIPELINE_ORDER: list[tuple[str, str, str]] = [
    # Phase 1 — user profile (skipped when analyze-company handoff is provided)
    ("hydrate_company_context", "1_user_profile", "Hydrate company summary or prepare analysis"),
    ("understand_company", "1_user_profile", "Understand company & crawl website"),
    ("analyze_user_instagram", "1_user_profile", "Analyze user Instagram"),
    ("analyze_user_linkedin", "1_user_profile", "Analyze user LinkedIn"),
    # Phase 2 — discovery
    ("propose_competitors", "2_discovery", "Propose competitors via OpenAI (user DNA + region)"),
    ("search_intelligence", "2_discovery", "Build search intelligence queries (fallback)"),
    ("discovery_pipeline", "2_discovery", "Discover competitors via Tavily/Firecrawl (fallback)"),
    ("find_competitors", "2_discovery", "Find competitors Instagram fallback"),
    ("discover_competitors", "2_discovery", "Fetch & rank competitor Instagram posts"),
    # Phase 3 — competitor analysis
    ("analyze_competitor_website", "3_competitor_social", "Analyze competitor websites"),
    ("analyze_competitor_instagram", "3_competitor_social", "Analyze competitor Instagram"),
    ("analyze_competitor_linkedin", "3_competitor_social", "Analyze competitor LinkedIn"),
    ("extract_post_data", "3_competitor_social", "Extract post data"),
    ("filter_duplicate_posts", "3_competitor_social", "Filter duplicate posts"),
    ("calculate_engagement", "3_competitor_social", "Calculate engagement"),
    ("extract_hashtags", "3_competitor_social", "Extract hashtags"),
    ("classify_topics", "3_competitor_social", "Classify topics"),
    ("analyze_content_mix", "3_competitor_social", "Analyze content mix"),
    # Phase 4 — strategy output
    ("similarity_analysis", "4_strategy", "Similarity analysis"),
    ("gap_analysis", "4_strategy", "Gap analysis"),
    ("competitor_intelligence", "4_strategy", "Competitor intelligence report"),
    ("recommendations", "4_strategy", "Generate recommendations"),
    ("generate_competitor_summary", "4_strategy", "Generate summary"),
]

PIPELINE_STEPS: dict[str, tuple[str, str]] = {
    name: (phase, label) for name, phase, label in PIPELINE_ORDER
}

STEP_INDEX: dict[str, int] = {name: idx + 1 for idx, (name, _, _) in enumerate(PIPELINE_ORDER)}
TOTAL_STEPS = len(PIPELINE_ORDER)

PHASE_TITLES: dict[str, str] = {
    "0_request": "REQUEST",
    "1_user_profile": "PHASE 1 — Analyze user profile (company + Instagram + LinkedIn)",
    "2_discovery": "PHASE 2 — Find competitors",
    "3_competitor_social": "PHASE 3 — Analyze competitor Instagram & LinkedIn",
    "4_strategy": "PHASE 4 — Similarity, gaps, SWOT & recommendations",
    "9_complete": "COMPLETE",
}

_last_phase_logged: str | None = None


def _format_details(**details: Any) -> str:
    if not details:
        return ""
    parts = [f"{key}={value}" for key, value in details.items() if value is not None]
    return (" | " + " ".join(parts)) if parts else ""


def log_event(phase: str, message: str, **details: Any) -> None:
    logger.info("[Competitor %s] %s%s", phase, message, _format_details(**details))


def log_phase_banner(phase: str) -> None:
    global _last_phase_logged
    if phase == _last_phase_logged:
        return
    _last_phase_logged = phase
    title = PHASE_TITLES.get(phase, phase)
    logger.info("=" * 72)
    logger.info("[Competitor] %s", title)
    logger.info("=" * 72)


def reset_pipeline_log_state() -> None:
    global _last_phase_logged
    _last_phase_logged = None


def log_pipeline_start(*, company: str, region: str | None = None, **details: Any) -> None:
    reset_pipeline_log_state()
    log_phase_banner("0_request")
    log_event(
        "0_request",
        "Pipeline run started",
        company=company,
        region=region,
        total_steps=TOTAL_STEPS,
        platforms="instagram+linkedin",
        **details,
    )
    logger.info(
        "[Competitor 0_request] Flow: "
        "1) user DNA (company+IG+LI) → 2) OpenAI propose ≥10 competitors → "
        "3) analyze competitor IG/LI → 4) strategy report"
    )


def log_pipeline_complete(*, status: str, duration_sec: float, **details: Any) -> None:
    log_phase_banner("9_complete")
    log_event(
        "9_complete",
        f"Pipeline finished ({status})",
        duration_sec=round(duration_sec, 2),
        **details,
    )


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
    }

    competitors = (
        state.get("verified_competitors")
        or state.get("discovered_influencers")
        or state.get("competitors")
        or []
    )
    if competitors:
        details["competitors"] = len(competitors)
    posts = state.get("processed_posts") or state.get("discovered_posts") or []
    if posts:
        details["posts"] = len(posts)
    if state.get("similarity_scores"):
        details["similarity_scores"] = len(state.get("similarity_scores") or [])
    if state.get("recommendations"):
        details["recommendations"] = len(state.get("recommendations") or [])
    if state.get("competitor_intelligence_report"):
        details["intelligence_report"] = "yes"
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
    """Wrap a graph node with start/done pipeline logging."""

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
                "[Competitor %s] FAILED [%s/%s] → %s | step=%s elapsed_sec=%.2f",
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
