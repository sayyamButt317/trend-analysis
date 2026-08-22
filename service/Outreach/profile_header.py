from __future__ import annotations
import asyncio
from playwright.async_api import Page


async def EnsureProfileHeaderView(page: Page) -> None:
    try:
        await page.evaluate("window.scrollTo(0, 0)")
    except Exception:
        pass
    await asyncio.sleep(0.6)
    try:
        await page.mouse.wheel(0, -4000)
    except Exception:
        pass
    await asyncio.sleep(0.4)
    for _ in range(12):
        ready = await page.evaluate(
            r"""() => {
                const nodes = Array.from(document.querySelectorAll(
                    'button, a, [role="button"], .artdeco-button'
                ));
                return nodes.some(el => {
                    const aria = (el.getAttribute('aria-label') || '');
                    const text = (el.innerText || '').trim().split('\n')[0].trim();
                    const r = el.getBoundingClientRect();
                    if (r.top < 40 || r.top > 560 || r.width < 2) return false;
                    return /invite.*connect/i.test(aria)
                        || /^\+?\s*connect\s*$/i.test(text)
                        || /^\s*message\s*$/i.test(text)
                        || /^\s*pending\s*$/i.test(text)
                        || /^\+?\s*follow\s*$/i.test(text)
                        || /^\s*more\s*$/i.test(text);
                });
            }"""
        )
        if ready:
            return await asyncio.sleep(0.45)
        
