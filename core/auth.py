"""Authentication functions for LinkedIn."""

import asyncio
import logging
import os
import time
from typing import Optional, Tuple
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from dotenv import load_dotenv

from .exceptions import AuthenticationError
from .utils import detect_rate_limit
from core.api_call_counter import record_api_call

logger = logging.getLogger(__name__)


def _mask_email(email: str) -> str:
    if "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    visible = local[:2] if len(local) >= 2 else local[:1]
    return f"{visible}***@{domain}"


async def warm_up_browser(page: Page) -> None:
    sites = [
        'https://www.google.com',
        'https://www.github.com',
    ]
    
    logger.info("Warming up browser by visiting normal sites...")
    
    for site in sites:
        try:
            await page.goto(site, wait_until='domcontentloaded', timeout=10000)
            await asyncio.sleep(1)  # Brief pause
            logger.debug(f"Visited {site}")
        except Exception as e:
            logger.debug(f"Could not visit {site}: {e}")
            continue
    
    logger.info("Browser warm-up complete")


def load_credentials_from_env() -> Tuple[Optional[str], Optional[str]]:
    load_dotenv()
    
    # Support both LINKEDIN_EMAIL and LINKEDIN_USERNAME
    email = os.getenv('LINKEDIN_EMAIL') or os.getenv('LINKEDIN_USERNAME')
    password = os.getenv('LINKEDIN_PASSWORD')
    
    return email, password


async def login_with_credentials(
    page: Page,
    email: Optional[str] = None,
    password: Optional[str] = None,
    timeout: int = 30000,
    warm_up: bool = True
) -> None:
    """
    Login to LinkedIn using email and password.
    
    Args:
        page: Playwright page object
        email: LinkedIn email (if None, tries to load from .env)
        password: LinkedIn password (if None, tries to load from .env)
        timeout: Timeout in milliseconds
        warm_up: Whether to warm up browser by visiting normal sites first
        
    Raises:
        AuthenticationError: If login fails
    """
    # Load from .env if not provided
    if not email or not password:
        env_email, env_password = load_credentials_from_env()
        email = email or env_email
        password = password or env_password
    
    if not email or not password:
        raise AuthenticationError(
            "LinkedIn credentials not provided. "
            "Either pass email/password parameters or set LINKEDIN_EMAIL "
            "and LINKEDIN_PASSWORD in your .env file."
        )
    # Warm up browser first to appear more human-like
    if warm_up:
        await warm_up_browser(page)
    logger.info("Logging in to LinkedIn...")
    
    try:
        # Navigate to login page
        record_api_call("linkedin", kind="playwright")
        await page.goto('https://www.linkedin.com/login', wait_until='domcontentloaded')
        # Check for rate limiting
        await detect_rate_limit(page)
        # Wait for login form
        try:
            await page.wait_for_selector('#username', timeout=timeout, state='visible')
        except PlaywrightTimeoutError:
            raise AuthenticationError(
                "Login form not found. LinkedIn may have changed their page structure "
                "or the site is experiencing issues."
            )
        
        # Fill in credentials
        await page.fill('#username', email)
        await page.fill('#password', password)
        logger.debug("Credentials entered")

        # Click sign in button
        await page.click('button[type="submit"]')
        
        # Wait for navigation
        try:
            await page.wait_for_url(
                lambda url: 'feed' in url or 'checkpoint' in url or 'authwall' in url,
                timeout=timeout
            )
        except PlaywrightTimeoutError:
            # Check if we're still on login page
            if 'login' in page.url:
                raise AuthenticationError(
                    "Login failed. Please check your credentials. "
                    "The page did not navigate after clicking sign in."
                )
        
        # Check for various post-login states
        current_url = page.url
        
        # Check for security checkpoint
        if 'checkpoint' in current_url or 'challenge' in current_url:
            raise AuthenticationError(
                "LinkedIn security checkpoint detected. "
                "You may need to verify your identity manually. "
                "Consider using session persistence after manual verification. "
                f"Current URL: {current_url}"
            )
        
        # Check for auth wall
        if 'authwall' in current_url:
            raise AuthenticationError(
                "Authentication wall encountered. "
                "LinkedIn may be blocking automated access. "
                f"Current URL: {current_url}"
            )
        
        # Verify we're logged in by polling is_logged_in()
        start_time = time.time()
        logged_in = False
        while (time.time() - start_time) * 1000 < 5000:
            if await is_logged_in(page):
                logger.info(
                    "LinkedIn login successful for %s (url=%s)",
                    _mask_email(email),
                    current_url,
                )
                logged_in = True
                break
            await asyncio.sleep(0.5)  # Poll every 500ms

        if not logged_in:
            if "feed" in current_url or "mynetwork" in current_url:
                logger.info(
                    "LinkedIn login successful for %s (url=%s, nav verification skipped)",
                    _mask_email(email),
                    current_url,
                )
            else:
                logger.warning(
                    "Could not verify LinkedIn login for %s (url=%s). Proceeding anyway...",
                    _mask_email(email),
                    current_url,
                )
    
    except asyncio.CancelledError:
        logger.warning(
            "LinkedIn login interrupted for %s (server reload or request cancelled)",
            _mask_email(email),
        )
        raise
    except PlaywrightTimeoutError as e:
        raise AuthenticationError(
            f"Login timed out: {e}. "
            "This could indicate network issues or LinkedIn blocking the request."
        )
    except Exception as e:
        if isinstance(e, AuthenticationError):
            raise
        if isinstance(e, asyncio.CancelledError):
            raise
        raise AuthenticationError(f"Unexpected error during login: {e}")


async def login_with_cookie(page: Page, cookie_value: str) -> None:
    logger.info("Logging in with cookie...")

    try:
        await page.context.add_cookies([{
            "name": "li_at",
            "value": cookie_value,
            "domain": ".linkedin.com",
            "path": "/"
        }])

        record_api_call("linkedin", kind="playwright")
        await page.goto('https://www.linkedin.com/feed/', wait_until='domcontentloaded')

        if 'login' in page.url or 'authwall' in page.url:
            raise AuthenticationError(
                "Cookie authentication failed. The cookie may be expired or invalid."
            )

        start_time = time.time()
        logged_in = False
        cookie_url = page.url
        while (time.time() - start_time) * 1000 < 5000:
            if await is_logged_in(page):
                logger.info("LinkedIn cookie login successful (url=%s)", cookie_url)
                logged_in = True
                break
            await asyncio.sleep(0.5)

        if not logged_in:
            if "feed" in cookie_url or "mynetwork" in cookie_url:
                logger.info(
                    "LinkedIn cookie login successful (url=%s, nav verification skipped)",
                    cookie_url,
                )
            else:
                logger.warning(
                    "Could not verify LinkedIn cookie login (url=%s). Proceeding anyway...",
                    cookie_url,
                )

    except Exception as e:
        if isinstance(e, AuthenticationError):
            raise
        raise AuthenticationError(f"Cookie authentication error: {e}")


async def is_logged_in(page: Page) -> bool:
    try:
        current_url = page.url
        auth_blockers = ['/login', '/authwall', '/checkpoint', '/challenge', '/uas/login', '/uas/consumer-email-challenge']
        if any(pattern in current_url for pattern in auth_blockers):
            return False
        old_selectors = '.global-nav__primary-link, [data-control-name="nav.settings"]'
        old_count = await page.locator(old_selectors).count()
        new_selectors = 'nav a[href*="/feed"], nav button:has-text("Home"), nav a[href*="/mynetwork"]'
        new_count = await page.locator(new_selectors).count()
        has_nav_elements = old_count > 0 or new_count > 0
        authenticated_only_pages = ['/feed', '/mynetwork', '/messaging', '/notifications']
        is_authenticated_page = any(pattern in current_url for pattern in authenticated_only_pages)
        return has_nav_elements or is_authenticated_page
    except Exception:
        return False


async def wait_for_manual_login(page: Page, timeout: int = 300000) -> None:

    logger.info(
        "⏳ Please complete the login process manually in the browser. "
        "Waiting up to 5 minutes..."
    )
    
    start_time = asyncio.get_event_loop().time()
    
    while True:
        if await is_logged_in(page):
            logger.info("LinkedIn manual login successful (url=%s)", page.url)
            return
        elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
        if elapsed > timeout:
            raise AuthenticationError(
                "Manual login timeout. Please try again and complete login faster."
            )
        
        # Wait a bit before checking again
        await asyncio.sleep(1)
