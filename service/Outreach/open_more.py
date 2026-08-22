import asyncio
from playwright.async_api import Page
from agents.outreach.pipeline_log import log_task
from service.Outreach.connect_debugging import SaveDebugScreenshot
from service.Outreach.human_click import HumanClickLocator
from service.Outreach.more_button import FindHeaderMoreButton
from service.Outreach.visible import ClickFirst
from service.Outreach.profile_header import EnsureProfileHeaderView
from service.Outreach.pending_header import PendingHeaderVisible
from service.Outreach.attempt import Attempt


async def withdraw_connection_request(page: Page) -> bool:
    async def _open_more() -> bool:
        more = await FindHeaderMoreButton(page)
        if more and await HumanClickLocator(page, more):
            return True
        return await ClickFirst(
            page,
            [
                'main button:text-is("More")',
                'button:text-is("More")',
                'button[aria-label*="More actions" i]',
            ],
            timeout=2500,
        )
    await Attempt("more_menu", _open_more)
    try:
        await page.reload(
            wait_until="domcontentloaded",
            timeout=30000,
        )
        await asyncio.sleep(2.0)
    except Exception as exc:
        log_task(
            "Reload after withdraw failed",
            error=str(exc)[:80],
        )
    await EnsureProfileHeaderView(page)
    still_pending = await PendingHeaderVisible(page)
    ok = not still_pending
    log_task(
        "Withdraw result",
        withdrawn=ok,
        still_pending=still_pending,
    )

    if not ok:
        await SaveDebugScreenshot(
            page,
            "withdraw_still_pending",
        )

    return ok