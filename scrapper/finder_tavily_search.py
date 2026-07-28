import asyncio
from collections.abc import Callable


async def run_limited_searches(
    queries: list[str],
    search_fn: Callable[[str], list[str]],
    *,
    concurrency: int = 2,
    delay_seconds: float = 0,
) -> dict[str, list[str]]:
    if not queries:
        return {}

    semaphore = asyncio.Semaphore(max(1, min(concurrency, 4)))
    results: dict[str, list[str]] = {}

    async def run_one(query: str) -> tuple[str, list[str]]:
        async with semaphore:
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
            urls = await asyncio.to_thread(search_fn, query)
            return query, urls

    pairs = await asyncio.gather(*(run_one(query) for query in queries))
    for query, urls in pairs:
        results[query] = urls
    return results
