from __future__ import annotations
import asyncio
from playwright.async_api import Page
from service.Outreach.linkedin_outreach import EnsureProfileHeaderView, PendingHeaderVisible
from agents.outreach.pipeline_log import log_task

async def _withdraw_pending_invitation(page: Page) -> bool:
    await EnsureProfileHeaderView(page)
    await asyncio.sleep(0.6)
    header_pending = await PendingHeaderVisible(page)
    log_task(
        "Withdrawing pending invitation to resend with note",
        header_pending=header_pending,
    )
    if not header_pending:
        await EnsureProfileHeaderView(page)
        await asyncio.sleep(1.0)
        header_pending = await PendingHeaderVisible(page)
        if not header_pending:
            log_task("No header Pending — nothing to withdraw")
            return False