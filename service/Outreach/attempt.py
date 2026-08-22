import asyncio
from playwright.async_api import Page
from agents.outreach.pipeline_log import log_task
from service.Outreach.confirm_withdraw import ConfirmWithdrawDialog
from service.Outreach.connect_debugging import SaveDebugScreenshot
from service.Outreach.pending_header import PendingHeaderVisible
from service.Outreach.profile_pendingbtn import ClickProfilePendingButton
from service.Outreach.withdraw_control import ClickWithdrawControl
from service.Outreach.visible import ClickFirst


async def _attempt(
    page: Page,
    label: str,
    opener,
) -> bool:
    log_task(f"Withdraw attempt via {label}")
    opened = await opener()
    if not opened:
        log_task(f"Could not open {label} for withdraw")
        return False
    await asyncio.sleep(0.9)
    if not await ClickWithdrawControl(page):
        log_task(f"Withdraw control missing after {label}")
        await SaveDebugScreenshot(
            page,
            f"withdraw_menu_miss_{label}",
        )
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        return False
    await ConfirmWithdrawDialog(page)
    await asyncio.sleep(1.6)
    return True


async def withdraw_connection_request(page: Page) -> bool:
    await _attempt(
        page,
        "pending_button",
        lambda: ClickProfilePendingButton(page),
    )

    if not await PendingHeaderVisible(page):
        log_task(
            "Withdraw result",
            withdrawn=True,
            via="pending_button",
        )
        return True

    log_task(
        "Withdraw result",
        withdrawn=False,
        via="pending_button",
    )

    return False