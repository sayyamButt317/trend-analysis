from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class InstagramFinderJob:
    job_id: str
    params: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    countries: list[str] = field(default_factory=list)
    total_found: int = 0
    total_new: int = 0
    total_existing: int = 0
    enriched: int = 0
    error: str | None = None
    influencers: list[dict[str, Any]] = field(default_factory=list)
    events: asyncio.Queue = field(default_factory=asyncio.Queue)

    def _upsert_influencer(self, influencer: dict[str, Any]) -> None:
        username = str(influencer.get("username") or "").lower()
        if not username:
            return
        for index, existing in enumerate(self.influencers):
            if str(existing.get("username") or "").lower() == username:
                self.influencers[index] = influencer
                return
        self.influencers.append(influencer)

    async def emit(self, event: dict[str, Any]) -> None:
        payload = {
            **event,
            "job_id": self.job_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        event_type = payload.get("type")
        if event_type == "started":
            self.status = "running"
            self.started_at = datetime.now(timezone.utc)
        elif event_type in {"influencer_found", "influencer_enriched"}:
            influencer = payload.get("influencer")
            if isinstance(influencer, dict):
                self._upsert_influencer(influencer)
            if event_type == "influencer_enriched":
                self.enriched += 1
        elif event_type == "completed":
            self.status = "completed"
            self.finished_at = datetime.now(timezone.utc)
            self.countries = list(payload.get("countries") or self.countries)
            self.total_found = int(payload.get("total_found") or self.total_found)
            self.total_new = int(payload.get("total_new") or self.total_new)
            self.total_existing = int(
                payload.get("total_existing") or self.total_existing
            )
            influencers = payload.get("influencers")
            if isinstance(influencers, list):
                self.influencers = influencers
        elif event_type == "error":
            self.status = "failed"
            self.finished_at = datetime.now(timezone.utc)
            self.error = payload.get("error")

        await self.events.put(payload)

    def to_status(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "params": self.params,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "countries": self.countries,
            "total_found": self.total_found,
            "total_new": self.total_new,
            "total_existing": self.total_existing,
            "enriched": self.enriched,
            "error": self.error,
            "influencers": self.influencers,
        }


_jobs: dict[str, InstagramFinderJob] = {}
_MAX_JOBS = 50


def create_finder_job(params: dict[str, Any]) -> InstagramFinderJob:
    while len(_jobs) >= _MAX_JOBS:
        oldest_id = next(iter(_jobs))
        _jobs.pop(oldest_id, None)

    job = InstagramFinderJob(job_id=str(uuid.uuid4()), params=params)
    _jobs[job.job_id] = job
    return job


def get_finder_job(job_id: str) -> InstagramFinderJob | None:
    return _jobs.get(job_id)
