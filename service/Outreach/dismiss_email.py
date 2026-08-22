from playwright.async_api import Page
from agents.outreach.pipeline_log import log_task
from service.Outreach.dialog import Dialogue
from service.Outreach.visible import ClickFirst


async def DismissEmailGate(page: Page) -> None:
    dialog = await Dialogue(page, timeout=1200)
    if not dialog:
        return
    text = ""
    try:
        text = (await dialog.inner_text()).lower()
    except Exception:
        pass
    if "email" not in text and "got it" not in text:
        return
    log_task("Dismissing email verification gate")
    await ClickFirst(
        page,
        [
            'button:has-text("Got it")',
            'button:has-text("Continue")',
            'button:has-text("Dismiss")',
            'button[aria-label="Dismiss"]',
        ],
        timeout=1500,
    )
