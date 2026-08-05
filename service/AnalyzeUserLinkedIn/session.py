from __future__ import annotations
import asyncio
import logging
import os
from pathlib import Path
from typing import Any
from core.api_call_counter import record_api_call
from core.auth import is_logged_in, load_credentials_from_env, login_with_cookie, login_with_credentials
from core.browser import BrowserManager, playwright_subprocess_supported, run_async_playwright_in_thread
from core.exceptions import AuthenticationError, RateLimitError
from core.utils import detect_rate_limit, handle_modal_close
from service.AnalyzeUserLinkedIn.safety import linkedin_human_delay, linkedin_safety_config

logger = logging.getLogger(__name__)


def invalidate_linkedin_session_cache(session_file: str | None = None) -> None:
    path = Path(session_file or linkedin_safety_config()["session_file"])
    if path.exists():
        path.unlink(missing_ok=True)
        logger.info("Cleared LinkedIn session cache at %s", path)


class LinkedInPlaywrightSession:
    def __init__(self, *, runtime: dict[str, Any] | None = None) -> None:
        self.safety = linkedin_safety_config(runtime)
        self._browser: BrowserManager | None = None
        self._pages_visited = 0
        self._blocked = False

    @property
    def page(self):
        if not self._browser:
            raise RuntimeError("LinkedIn session not started")
        return self._browser.page

    @property
    def is_blocked(self) -> bool:
        return self._blocked

    async def __aenter__(self) -> LinkedInPlaywrightSession:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close(save_session=exc_type is None and not self._blocked)

    async def start(self) -> None:
        self._browser = BrowserManager(
            headless=True,
            slow_mo=self.safety["slow_mo_ms"],
        )
        try:
            await self._browser.start()
            logger.info(
                "LinkedIn Playwright session starting (avoid file saves while using uvicorn --reload)"
            )

            session_path = self.safety["session_file"]
            if self.safety["reuse_session"] and Path(session_path).exists():
                try:
                    await self._browser.load_session(session_path)
                    await self.navigate("https://www.linkedin.com/feed/", purpose="session_check")
                    if await is_logged_in(self.page):
                        logger.info("LinkedIn session restored from cache")
                        return
                    logger.info("Cached LinkedIn session expired — logging in again")
                    invalidate_linkedin_session_cache(session_path)
                except (AuthenticationError, RateLimitError):
                    invalidate_linkedin_session_cache(session_path)
                    raise
                except Exception:
                    logger.info("Could not restore LinkedIn session cache — fresh login")
                    invalidate_linkedin_session_cache(session_path)

            li_at = (os.getenv("LINKEDIN_LI_AT") or "").strip()
            if li_at:
                await login_with_cookie(self.page, li_at)
                self._browser.is_authenticated = True
                return

            email, password = load_credentials_from_env()
            if not email or not password:
                raise AuthenticationError(
                    "LinkedIn credentials not configured. Set LINKEDIN_EMAIL/LINKEDIN_PASSWORD "
                    "or LINKEDIN_LI_AT (li_at cookie from browser after manual login)."
                )

            await login_with_credentials(
                self.page,
                email,
                password,
                warm_up=self.safety["warm_up_browser"],
            )
            self._browser.is_authenticated = True
        except asyncio.CancelledError:
            logger.warning("LinkedIn session startup interrupted — closing browser")
            await self.close(save_session=False)
            raise
        except (AuthenticationError, RateLimitError):
            invalidate_linkedin_session_cache(self.safety["session_file"])
            await self.close(save_session=False)
            raise
        except Exception:
            await self.close(save_session=False)
            raise

    async def close(self, *, save_session: bool = True) -> None:
        if not self._browser:
            return
        browser = self._browser
        self._browser = None
        session_path = self.safety["session_file"]
        try:
            if save_session and self.safety["reuse_session"] and browser.is_authenticated:
                try:
                    Path(session_path).parent.mkdir(parents=True, exist_ok=True)
                    await browser.save_session(session_path)
                except Exception:
                    logger.warning("Failed to save LinkedIn session cache", exc_info=True)
        finally:
            await browser.close()

    async def navigate(self, url: str, *, purpose: str = "page") -> bool:
        if self._blocked:
            return False
        if self._pages_visited >= self.safety["max_pages_per_session"]:
            logger.warning(
                "LinkedIn page budget reached (%s) — skipping %s",
                self.safety["max_pages_per_session"],
                purpose,
            )
            return False

        if self._pages_visited > 0:
            await linkedin_human_delay(self.safety)

        try:
            record_api_call("linkedin", kind="playwright")
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await linkedin_human_delay(self.safety)
            await detect_rate_limit(self.page)
            await handle_modal_close(self.page)

            if not await is_logged_in(self.page):
                self._blocked = True
                raise AuthenticationError(
                    "LinkedIn session is not authenticated (login wall or checkpoint). "
                    "Stop automation and verify the account manually."
                )

            self._pages_visited += 1
            return True
        except RateLimitError:
            self._blocked = True
            logger.error("LinkedIn rate limit detected during %s — stopping further pages", purpose)
            raise
        except AuthenticationError:
            self._blocked = True
            raise
        except Exception:
            logger.warning("LinkedIn navigation failed for %s (%s)", purpose, url, exc_info=True)
            return False


async def run_linkedin_playwright(coro_factory) -> Any:
    if playwright_subprocess_supported():
        return await coro_factory()
    return await run_async_playwright_in_thread(coro_factory)
