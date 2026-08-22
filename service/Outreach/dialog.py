from playwright.async_api import Page
from service.Outreach.visible import FirstVisible

async def Dialogue(page: Page, *, timeout: int = 4000):
    return await FirstVisible(
        page,
        [
            'div[role="dialog"]',
            "div.artdeco-modal-overlay",
            "div.artdeco-modal",
            "div.send-invite",
            "div.artdeco-modal__actionbar",
            "div.artdeco-modal__content",
            'div:has(> h2:has-text("Add a note"))',
            'h2:has-text("Add a note to your invitation")',
        ],
        timeout=timeout,
    )