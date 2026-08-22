from playwright.async_api import Page
from agents.outreach.pipeline_log import log_task
from service.Outreach.more_button import FindHeaderMoreButton
from service.Outreach.profile_header import EnsureProfileHeaderView
from service.Outreach.visible import ListVisibleActionButtons
from service.Outreach.pending_header import PendingHeaderVisible
from service.Outreach.primary_connect import ProfileHasPrimaryConnect
from service.Outreach.constants import CONNECT_BUTTON_SELECTORS, FOLLOW_SELECTORS
from service.Outreach.visible_button import FirstVisible


async def DetectConnectionStatus(page: Page) -> str:
    await EnsureProfileHeaderView(page)
    actions = await ListVisibleActionButtons(page, limit=20)
    log_task("Status probe actions", buttons=", ".join(actions[:12]) or "none")

    # Only trust header/action-row Pending — loose PENDING_SELECTORS match sidebar noise.
    pending_hit = await PendingHeaderVisible(page)
    has_connect = await ProfileHasPrimaryConnect(page)
    has_more = bool(await FindHeaderMoreButton(page))
    has_follow = bool(await FirstVisible(page, FOLLOW_SELECTORS, timeout=1200))
    has_message = bool(
        await FirstVisible(
            page,
            [
                'main a:text-is("Message")',
                'main button:text-is("Message")',
                'main a:has-text("Message")',
                'a:text-is("Message")',
                'button:text-is("Message")',
                'button:has-text("Message")',
            ],
            timeout=1200,
        )
    )
    log_task(
        "Status probe flags",
        is_pending=pending_hit,
        connect=has_connect,
        more=has_more,
        follow=has_follow,
        has_message=has_message,
    )
    if pending_hit:
        return "pending"
    if has_connect:
        return "not_connected"
    if has_more or has_follow:
        return "not_connected"
    if has_message and not has_connect:
        return "connected"
    if await FirstVisible(page, CONNECT_BUTTON_SELECTORS, timeout=800):
        return "not_connected"
    return "unknown"