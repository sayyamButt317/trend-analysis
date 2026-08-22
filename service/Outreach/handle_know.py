import asyncio
from playwright.async_api import Page
from agents.outreach.pipeline_log import log_task
from service.Outreach.dialog import Dialogue
from service.Outreach.visible import ClickFirst


async def HandleHowDoYouKnow(page: Page) -> None:
    dialog = await Dialogue(page, timeout=2000)
    if not dialog:
        return
    text = ""
    try:
        text = (await dialog.inner_text()).lower()
    except Exception:
        return
    if "how do you know" not in text and "other" not in text:
        return
    log_task("Handling 'How do you know this person?' dialog")
    await ClickFirst(
        page,
        [
            'label:has-text("Other")',
            'button:has-text("Other")',
            'input[value="OTHER"]',
            '[aria-label*="Other" i]',
        ],
        timeout=2000,
    )
    await asyncio.sleep(0.4)
    await ClickFirst(
        page,
        [
            'button:has-text("Connect")',
            'button:has-text("Next")',
            'button:has-text("Continue")',
            'button[aria-label*="Connect" i]',
        ],
        timeout=2500,
    )
    await asyncio.sleep(0.8)
