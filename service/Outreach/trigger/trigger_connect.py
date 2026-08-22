from __future__ import annotations
import asyncio
from playwright.async_api import Page
from agents.outreach.pipeline_log import log_task
from service.Outreach.click_connect import ClickConnectViaPlayWrightRole, ClickElementHandle, JsClickConnectInProfile
from service.Outreach.click_menu_connect import JsClickMenuConnect
from service.Outreach.connect_button import ResolveHeaderConnectButton
from service.Outreach.connect_debugging import SaveDebugScreenshot
from service.Outreach.dismiss_blocking_overlay import DismissBlockingOverlays
from service.Outreach.invite_ui import WaitForInviteUi
from service.Outreach.menu_connect import ClickConnectInOpenMenu
from service.Outreach.open_connectfrom_menu import OpenConnectFromMoreMenu
from service.Outreach.primary_connect import ProfileHasPrimaryConnect
from service.Outreach.profile_card import ProfileRoot
from service.Outreach.profile_display import ProfilePersonName
from service.Outreach.profile_header import EnsureProfileHeaderView
from service.Outreach.visible_button import ListVisibleActionButtons



async def TriggerConnect(page: Page) -> str:
    await EnsureProfileHeaderView(page)
    await DismissBlockingOverlays(page)
    try:
        h1 = page.locator("main h1").first
        await h1.scroll_into_view_if_needed(timeout=5000)
        await asyncio.sleep(0.5)
    except Exception:
        try:
            card = await ProfileRoot(page)
            await card.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
        except Exception:
            pass

    buttons = await ListVisibleActionButtons(page)
    log_task("Profile card actions", buttons=", ".join(buttons[:15]) or "none")

    has_primary = await ProfileHasPrimaryConnect(page)
    if not has_primary:
        log_task("No primary Connect — trying More → Connect (Premium layout)")
        if await OpenConnectFromMoreMenu(page):
            state = await WaitForInviteUi(page, timeout_ms=8000, accept_menu=False)
            log_task("Invite UI after More → Connect", state=state)
            if state in {"dialog", "invite_controls", "pending"}:
                return state
            if await ClickConnectInOpenMenu(page, await ProfilePersonName(page)):
                state = await WaitForInviteUi(page, timeout_ms=8000, accept_menu=False)
                log_task("Invite UI after More → Connect retry", state=state)
                if state in {"dialog", "invite_controls", "pending"}:
                    return state
            await SaveDebugScreenshot(page, "premium_more_connect_noDialogue")
            try:
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
            except Exception:
                pass

    log_task("Trying profile-header Connect with real mouse click")
    if await ClickConnectViaPlayWrightRole(page):
        state = await WaitForInviteUi(page, timeout_ms=12000, accept_menu=False)
        log_task("Invite UI after profile Connect click", state=state)
        if state == "menu":
            await JsClickMenuConnect(page)
            state = await WaitForInviteUi(page, timeout_ms=6000, accept_menu=False)
        if state in {"dialog", "invite_controls", "pending"}:
            return state
        await SaveDebugScreenshot(page, "after_connect_click")
        element, _ = await ResolveHeaderConnectButton(page)
        if element:
            log_task("Retry Connect via focus + Enter")
            try:
                await element.focus()
                await page.keyboard.press("Enter")
            except Exception:
                await ClickElementHandle(page, element)
            state = await WaitForInviteUi(page, timeout_ms=8000, accept_menu=False)
            log_task("Invite UI after Enter retry", state=state)
            if state in {"dialog", "invite_controls", "pending"}:
                return state

    log_task("Trying JS Connect click in profile card")
    if await JsClickConnectInProfile(page):
        state = await WaitForInviteUi(page, timeout_ms=10000, accept_menu=False)
        log_task("Invite UI after JS Connect click", state=state)
        if state in {"dialog", "invite_controls", "pending"}:
            return state

    if has_primary:
        log_task("Fallback More → Connect on profile card")
        if await OpenConnectFromMoreMenu(page):
            state = await WaitForInviteUi(page, timeout_ms=10000, accept_menu=False)
            log_task("Invite UI after More → Connect", state=state)
            if state in {"dialog", "invite_controls", "pending"}:
                return state
    return "none"