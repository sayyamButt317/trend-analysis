import asyncio
from playwright.async_api import Page

from agents.outreach.pipeline_log import log_task

async def HumanClickLocator(page: Page, locator) -> bool:
    """Real mouse click via bounding box — Ember/LinkedIn often ignores synthetic clicks."""
    try:
        await locator.scroll_into_view_if_needed(timeout=5000)
        await asyncio.sleep(0.35)
        box = await locator.bounding_box()
        if not box:
            await locator.click(timeout=4000, force=True)
            return True
        x = box["x"] + box["width"] * 0.5
        y = box["y"] + box["height"] * 0.5
        log_task("Mouse click at", x=round(x, 1), y=round(y, 1), w=round(box["width"], 1), h=round(box["height"], 1))
        await page.mouse.move(x, y, steps=12)
        await asyncio.sleep(0.2)
        await page.mouse.down()
        await asyncio.sleep(0.05)
        await page.mouse.up()
        return True
    except Exception as exc:
        log_task("Human click failed, trying force click", error=str(exc)[:80])
        try:
            await locator.click(timeout=4000, force=True, delay=80)
            return True
        except Exception:
            try:
                await locator.evaluate("el => el.click()")
                return True
            except Exception:
                return False
