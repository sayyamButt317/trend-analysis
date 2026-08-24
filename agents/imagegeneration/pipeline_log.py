from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger("imagegeneration.pipeline")

NodeFn = Callable[[Any], Awaitable[Any]]


def log_event(phase: str, message: str, **fields: Any) -> None:
    extras = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    logger.info("[%s] %s%s", phase, message, f" | {extras}" if extras else "")


def log_pipeline_start(**fields: Any) -> None:
    log_event("start", "Image generation pipeline started", **fields)


def log_pipeline_complete(**fields: Any) -> None:
    log_event("complete", "Image generation pipeline finished", **fields)


def with_pipeline_log(node_name: str, node_fn: NodeFn) -> NodeFn:
    async def wrapper(state: Any) -> Any:
        started = time.perf_counter()
        log_event("node", f"Enter {node_name}")
        try:
            result = await node_fn(state)
            log_event(
                "node",
                f"Exit {node_name}",
                elapsed_sec=round(time.perf_counter() - started, 2),
            )
            return result
        except Exception:
            log_event(
                "node",
                f"Fail {node_name}",
                elapsed_sec=round(time.perf_counter() - started, 2),
            )
            raise

    wrapper.__name__ = getattr(node_fn, "__name__", node_name)
    return wrapper
