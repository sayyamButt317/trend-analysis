from playwright.async_api import Page

from service.Outreach.connect_button import ResolveHeaderConnectButton
from service.Outreach.locate_connect import FindProfileConnectLocator

async def ProfileHasPrimaryConnect(page: Page) -> bool:
    """True when Invite/Connect is a visible primary header CTA (non-Premium layout)."""
    locator, _ = await FindProfileConnectLocator(page)
    if locator:
        try:
            return await locator.is_visible()
        except Exception:
            return False
    info, _ = await ResolveHeaderConnectButton(page)
    return bool(info)
