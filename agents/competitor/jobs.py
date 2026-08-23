"""Background jobs for long-running competitor analysis (avoids gateway 504)."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from agents.trend.schemas.competitor_request import CompetitorAnalysisRequest

logger = logging.getLogger("competitor.jobs")

_jobs: dict[str, dict[str, Any]] = {}
_lock = asyncio.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_competitor_job(request: CompetitorAnalysisRequest) -> dict[str, Any]:
    job_id = str(uuid.uuid4())
    company = request.normalized_company()
    snapshot = {
        "job_id": job_id,
        "status": "queued",
        "created_at": _now(),
        "updated_at": _now(),
        "company_name": company.get("name") or request.company_name,
        "company_id": request.company_id,
        "region": request.region,
        "competitor_limit": request.competitor_limit,
        "error": None,
        "analysis_id": None,
        "prompt_id": None,
        "result": None,
        "elapsed_sec": None,
    }
    async with _lock:
        _jobs[job_id] = snapshot

    asyncio.create_task(_run_competitor_job(job_id, request), name=f"competitor-job-{job_id}")
    return {
        "success": True,
        "job_id": job_id,
        "status": "queued",
        "message": (
            "Competitor analysis started. Poll GET /competitor-analysis/jobs/{job_id} "
            "until status is completed or failed. Full results are preserved."
        ),
        "poll_url": f"/competitor-analysis/jobs/{job_id}",
        "created_at": snapshot["created_at"],
    }


async def get_competitor_job(job_id: str) -> dict[str, Any] | None:
    async with _lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        return dict(job)


async def _update_job(job_id: str, **fields: Any) -> None:
    async with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job.update(fields)
        job["updated_at"] = _now()


async def _run_competitor_job(job_id: str, request: CompetitorAnalysisRequest) -> None:
    from agents.competitor.invoke.competitor_invoke import competitorAnalysisAgent

    started = time.time()
    await _update_job(job_id, status="running")
    logger.info("Competitor job started job_id=%s company=%s", job_id, request.company_name)
    try:
        result = await competitorAnalysisAgent(request)
        meta = (result or {}).get("meta") or {}
        await _update_job(
            job_id,
            status="completed",
            result=result,
            company_id=meta.get("company_id") or request.company_id,
            analysis_id=meta.get("analysis_id"),
            prompt_id=meta.get("prompt_id"),
            elapsed_sec=round(time.time() - started, 3),
            error=result.get("error") if isinstance(result, dict) else None,
        )
        logger.info(
            "Competitor job completed job_id=%s company_id=%s elapsed_sec=%.1f",
            job_id,
            meta.get("company_id") or request.company_id,
            time.time() - started,
        )
    except Exception as exc:
        logger.exception("Competitor job failed job_id=%s", job_id)
        await _update_job(
            job_id,
            status="failed",
            error=str(exc),
            elapsed_sec=round(time.time() - started, 3),
            result=None,
        )
