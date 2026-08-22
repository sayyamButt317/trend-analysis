import asyncio
from playwright.async_api import Page

async def DismissBlockingOverlays(page: Page) -> None:
    try:
        await page.evaluate(
            """() => {
                const texts = /accept|agree|got it|dismiss|not now|no thanks|skip/i;
                for (const btn of document.querySelectorAll('button')) {
                    const t = ((btn.innerText || '') + ' ' + (btn.getAttribute('aria-label') || '')).trim();
                    if (!texts.test(t)) continue;
                    const rect = btn.getBoundingClientRect();
                    if (rect.width < 2 || rect.height < 2) continue;
                    btn.click();
                }
            }"""
        )
    except Exception:
        pass
    try:
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.25)
    except Exception:
        pass
