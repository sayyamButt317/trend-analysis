import asyncio
from playwright.async_api import Page
from agents.outreach.pipeline_log import log_task
from service.Outreach.visible_button import FirstVisible
from service.Outreach.connection_available import ProfileConnectStillAvailable
from service.Outreach.pending_header import PendingHeaderVisible
from service.Outreach.profile_header import EnsureProfileHeaderView

async def InvitationConfirmed(page: Page) -> bool:
    """Confirm invite: Pending button, toast, or Connect CTA gone."""
    await EnsureProfileHeaderView(page)
    await asyncio.sleep(1.0)
    if await PendingHeaderVisible(page):
        return True
    toast = await FirstVisible(
        page,
        [
            'div[data-test-artdeco-toast-item]:has-text("Invitation sent")',
            '.artdeco-toast-item__message:has-text("Invitation sent")',
            'div:has-text("Invitation sent to")',
        ],
        timeout=1500,
    )
    if toast:
        return True
    if await ProfileConnectStillAvailable(page):
        log_task("Invite still available — not confirmed")
        return False
    return False
