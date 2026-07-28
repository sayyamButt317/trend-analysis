import logging

from scrapper.instagram_finder.finder import find_gcc_influencers
from scrapper.instagram_finder.job_progress import get_finder_job

logger = logging.getLogger(__name__)


async def run_instagram_finder_job(job_id: str) -> None:
    job = get_finder_job(job_id)
    if not job:
        logger.error("Instagram finder job %s not found", job_id)
        return

    params = job.params
    await job.emit({"type": "started", "params": params})

    try:
        result = await find_gcc_influencers(
            countries=params.get("countries"),
            max_count=params.get("max_count", 10),
            enrich_profiles=params.get("enrich_profiles", True),
            job=job,
        )
        if not result.get("success"):
            await job.emit({"type": "error", "error": result.get("error")})
            return

        await job.emit({"type": "completed", **result})
    except Exception as exc:
        logger.exception("Instagram finder job %s failed", job_id)
        await job.emit({"type": "error", "error": str(exc)})
