from core.api_call_counter import bind_stats_to_thread, get_api_call_stats
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from .exceptions import NetworkError

logger = logging.getLogger(__name__)

T = TypeVar("T")


def configure_windows_event_loop() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def playwright_subprocess_supported() -> bool:
    """Return False when the active loop cannot spawn subprocesses (Playwright on Windows)."""
    if sys.platform != "win32":
        return True
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return isinstance(
            asyncio.get_event_loop_policy(),
            asyncio.WindowsProactorEventLoopPolicy,
        )
    loop_name = type(loop).__name__
    if "Selector" in loop_name:
        return False
    # Inside FastAPI/uvicorn on Windows, prefer the thread runner even with Proactor.
    return False


async def _close_with_timeout(awaitable: Awaitable[Any], label: str, timeout: float = 5.0) -> None:
    try:
        await asyncio.wait_for(awaitable, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("Timed out closing %s", label)
    except Exception as exc:
        logger.debug("Error closing %s: %s", label, exc)


async def run_async_playwright_in_thread(
    coro_factory: Callable[[], Awaitable[T]],
) -> T:
    parent_stats = get_api_call_stats()

    def _runner() -> T:
        bind_stats_to_thread(parent_stats)
        configure_windows_event_loop()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro_factory())
        except BaseException:
            raise
        finally:
            try:
                pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()

    return await asyncio.to_thread(_runner)


class BrowserManager:
    """Async context manager for Playwright browser lifecycle."""
    
    def __init__(
        self,
        headless: bool = True,
        slow_mo: int = 0,
        viewport: Optional[Dict[str, int]] = None,
        user_agent: Optional[str] = None,
        **launch_options: Any
    ):
        """
        Initialize browser manager.
        
        Args:
            headless: Run browser in headless mode
            slow_mo: Slow down operations by specified milliseconds
            viewport: Browser viewport size (default: 1280x720)
            user_agent: Custom user agent string
            **launch_options: Additional Playwright launch options
        """
        self.headless = headless
        self.slow_mo = slow_mo
        self.viewport = viewport or {"width": 1280, "height": 720}
        self.user_agent = user_agent
        self.launch_options = launch_options
        
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._is_authenticated = False
    
    async def __aenter__(self) -> "BrowserManager":
        """Start browser and create context."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close browser and cleanup."""
        await self.close()
    
    async def start(self) -> None:
        """Start Playwright and launch browser."""
        try:
            self._playwright = await async_playwright().start()
            
            # Launch browser
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                **self.launch_options
            )
            
            logger.info(f"Browser launched (headless={self.headless})")
            
            # Create context
            context_options: Dict[str, Any] = {
                "viewport": self.viewport,
            }
            
            if self.user_agent:
                context_options["user_agent"] = self.user_agent
            
            self._context = await self._browser.new_context(**context_options)
            
            # Create initial page
            self._page = await self._context.new_page()
            
            logger.info("Browser context and page created")
            
        except Exception as e:
            await self.close()
            raise NetworkError(f"Failed to start browser: {e}")
    
    async def close(self) -> None:
        """Close browser and cleanup resources."""
        page = self._page
        context = self._context
        browser = self._browser
        playwright = self._playwright
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

        if page:
            await _close_with_timeout(page.close(), "page")
        if context:
            await _close_with_timeout(context.close(), "context")
        if browser:
            await _close_with_timeout(browser.close(), "browser")
        if playwright:
            await _close_with_timeout(playwright.stop(), "playwright")

        logger.info("Browser closed")
    
    async def new_page(self) -> Page:
        """
        Create a new page in the current context.
        
        Returns:
            New Playwright page
        """
        if not self._context:
            raise RuntimeError("Browser context not initialized. Call start() first.")
        
        page = await self._context.new_page()
        return page
    
    @property
    def page(self) -> Page:
        """
        Get the main page.
        
        Returns:
            Main Playwright page
        """
        if not self._page:
            raise RuntimeError("Browser not started. Use async context manager or call start().")
        return self._page
    
    @property
    def context(self) -> BrowserContext:
        """
        Get the browser context.
        
        Returns:
            Playwright browser context
        """
        if not self._context:
            raise RuntimeError("Browser context not initialized.")
        return self._context
    
    @property
    def browser(self) -> Browser:
        """
        Get the browser instance.
        
        Returns:
            Playwright browser
        """
        if not self._browser:
            raise RuntimeError("Browser not started.")
        return self._browser
    
    async def save_session(self, filepath: str) -> None:
        """
        Save browser session (cookies and storage) to file.
        
        Args:
            filepath: Path to save session file
        """
        if not self._context:
            raise RuntimeError("No browser context to save")
        
        storage_state = await self._context.storage_state()
        
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(storage_state, f, indent=2)
        
        logger.info(f"Session saved to {filepath}")
    
    async def load_session(self, filepath: str) -> None:
        """
        Load browser session from file.
        
        Args:
            filepath: Path to session file
        """
        if not Path(filepath).exists():
            raise FileNotFoundError(f"Session file not found: {filepath}")
        
        # Close existing context and create new one with stored state
        if self._context:
            await self._context.close()
        
        if not self._browser:
            raise RuntimeError("Browser not started")
        
        self._context = await self._browser.new_context(
            storage_state=filepath,
            viewport=self.viewport,
            user_agent=self.user_agent
        )
        
        # Create new page
        if self._page:
            await self._page.close()
        self._page = await self._context.new_page()
        
        self._is_authenticated = True
        
        logger.info(f"Session loaded from {filepath}")
    
    async def set_cookie(self, name: str, value: str, domain: str = ".linkedin.com") -> None:
        """
        Set a single cookie.
        
        Args:
            name: Cookie name
            value: Cookie value
            domain: Cookie domain
        """
        if not self._context:
            raise RuntimeError("No browser context")
        
        await self._context.add_cookies([{
            "name": name,
            "value": value,
            "domain": domain,
            "path": "/"
        }])
        
        logger.debug(f"Cookie set: {name}")
    
    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        return self._is_authenticated
    
    @is_authenticated.setter
    def is_authenticated(self, value: bool) -> None:
        """Set authentication status."""
        self._is_authenticated = value
