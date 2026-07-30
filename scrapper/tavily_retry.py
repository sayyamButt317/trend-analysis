import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_NON_RETRYABLE_MARKERS = (
    "getaddrinfo failed",
    "failed to resolve",
    "name resolution",
    "network is unreachable",
    "temporary failure in name resolution",
    "nodename nor servname provided",
)


def is_tavily_unreachable_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _NON_RETRYABLE_MARKERS)


def _is_non_retryable_error(exc: Exception) -> bool:
    return is_tavily_unreachable_error(exc)


def tavily_search_with_retry(
    client: Any,
    *,
    max_attempts: int = 3,
    backoff_seconds: float = 1.5,
    **search_kwargs: Any,
) -> dict | None:
    query_preview = (search_kwargs.get("query") or "")[:80]
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return client.search(**search_kwargs)
        except Exception as exc:
            last_exc = exc
            if _is_non_retryable_error(exc):
                logger.warning(
                    "Tavily unreachable (DNS/network); skipping search query=%r: %s",
                    query_preview,
                    exc,
                )
                return None
            if attempt < max_attempts:
                logger.warning(
                    "Tavily search failed (attempt %s/%s) query=%r: %s",
                    attempt,
                    max_attempts,
                    query_preview,
                    exc,
                )
                time.sleep(backoff_seconds * attempt)
                continue

            logger.warning(
                "Tavily search failed after %s attempts query=%r: %s",
                max_attempts,
                query_preview,
                last_exc,
            )
    return None
