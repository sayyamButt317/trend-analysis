from __future__ import annotations
import contextvars
import threading
from dataclasses import dataclass, field
from typing import Any

_stats_var: contextvars.ContextVar["ApiCallStats | None"] = contextvars.ContextVar(
    "api_call_stats",
    default=None,
)
_thread_local = threading.local()


@dataclass
class ApiCallStats:
    tavily: int = 0
    instagram: int = 0
    linkedin: int = 0
    firecrawl: int = 0

    tavily_search: int = 0
    tavily_extract: int = 0
    linkedin_playwright_pages: int = 0
    linkedin_tavily: int = 0
    firecrawl_scrape: int = 0
    firecrawl_search: int = 0

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def add(self, provider: str, *, n: int = 1, kind: str | None = None) -> None:
        with self._lock:
            if provider == "tavily":
                self.tavily += n
                if kind == "extract":
                    self.tavily_extract += n
                else:
                    self.tavily_search += n
            elif provider == "instagram":
                self.instagram += n
            elif provider == "linkedin":
                self.linkedin += n
                if kind == "playwright":
                    self.linkedin_playwright_pages += n
                else:
                    self.linkedin_tavily += n
            elif provider == "firecrawl":
                self.firecrawl += n
                if kind == "search":
                    self.firecrawl_search += n
                else:
                    self.firecrawl_scrape += n

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "tavily_calls": self.tavily,
                "instagram_calls": self.instagram,
                "linkedin_calls": self.linkedin,
                "firecrawl_calls": self.firecrawl,
                "breakdown": {
                    "tavily_search": self.tavily_search,
                    "tavily_extract": self.tavily_extract,
                    "linkedin_playwright_pages": self.linkedin_playwright_pages,
                    "linkedin_tavily": self.linkedin_tavily,
                    "firecrawl_scrape": self.firecrawl_scrape,
                    "firecrawl_search": self.firecrawl_search,
                },
            }


def begin_api_call_stats() -> ApiCallStats:
    stats = ApiCallStats()
    _stats_var.set(stats)
    _thread_local.stats = stats
    return stats


def get_api_call_stats() -> ApiCallStats | None:
    stats = _stats_var.get()
    if stats is not None:
        return stats
    return getattr(_thread_local, "stats", None)


def end_api_call_stats() -> dict[str, Any]:
    stats = get_api_call_stats()
    snapshot = stats.snapshot() if stats else {
        "tavily_calls": 0,
        "instagram_calls": 0,
        "linkedin_calls": 0,
        "firecrawl_calls": 0,
        "breakdown": {},
    }
    _stats_var.set(None)
    if hasattr(_thread_local, "stats"):
        _thread_local.stats = None
    return snapshot


def record_api_call(provider: str, *, n: int = 1, kind: str | None = None) -> None:
    stats = get_api_call_stats()
    if stats is None:
        return
    stats.add(provider, n=n, kind=kind)


def bind_stats_to_thread(stats: ApiCallStats | None) -> None:
    _thread_local.stats = stats
    if stats is not None:
        _stats_var.set(stats)
