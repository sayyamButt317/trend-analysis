from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

logger = logging.getLogger("contentrecommendation.pipeline")

NodeFn = Callable[[Any], Awaitable[Any]]


def log_event(phase: str, message: str, **fields: Any) -> None:
    extras = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    logger.info("[%s] %s%s", phase, message, f" | {extras}" if extras else "")


def log_pipeline_start(**fields: Any) -> None:
    log_event("start", "Content recommendation pipeline started", **fields)


def log_pipeline_complete(**fields: Any) -> None:
    log_event("complete", "Content recommendation pipeline finished", **fields)


def with_pipeline_log(node_name: str, node_fn: NodeFn) -> NodeFn:
    @wraps(node_fn)
    async def wrapper(state: Any) -> Any:
        log_event("node", f"Enter {node_name}")
        result = await node_fn(state)
        log_event("node", f"Exit {node_name}")
        return result

    return wrapper
