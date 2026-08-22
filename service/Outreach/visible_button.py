from __future__ import annotations
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from service.Outreach.human_click import HumanClickLocator


async def FirstVisible(page: Page, selectors: list[str], *, timeout: int = 2500, root=None):
    scope = root if root is not None else page
    for selector in selectors:
        try:
            locator = scope.locator(selector).first
            await locator.wait_for(state="visible", timeout=timeout)
            return locator
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue
    return None


async def ClickFirst(
    page: Page,
    selectors: list[str],
    *,
    timeout: int = 2500,
    root=None,
) -> bool:
    locator = await FirstVisible(page, selectors, timeout=timeout, root=root)
    if not locator:
        return False
    return await HumanClickLocator(page, locator)


async def ListVisibleActionButtons(page: Page, *, limit: int = 25) -> list[str]:
    """List buttons near the profile h1 (header actions only)."""
    try:
        return await page.evaluate(
            """(limit) => {
                const h1 = document.querySelector('main h1');
                let root = h1 && (h1.closest('section') || h1.closest('.artdeco-card'));
                if (!root) root = document.querySelector('main');
                if (!root) return [];
                const nodes = Array.from(root.querySelectorAll('button, a, [role="button"], .artdeco-button'));
                const labels = [];
                for (const btn of nodes) {
                    const style = window.getComputedStyle(btn);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    const rect = btn.getBoundingClientRect();
                    if (rect.width < 2 || rect.height < 2) continue;
                    if (rect.top > 560) continue;
                    const text = (btn.innerText || btn.getAttribute('aria-label') || '').trim().replace(/\\s+/g, ' ');
                    if (!text) continue;
                    labels.push(text.slice(0, 100));
                    if (labels.length >= limit) break;
                }
                return labels;
            }""",
            limit,
        )
    except Exception:
        return []
