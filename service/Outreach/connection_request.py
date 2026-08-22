import asyncio
from typing import Any
from playwright.async_api import Page
from agents.outreach.pipeline_log import log_task
from service.Outreach.connect_debugging import DumpConnectDom, SaveDebugScreenshot
from service.Outreach.handle_know import HandleHowDoYouKnow
from service.Outreach.invite_dialog import InviteDialogIsReal
from service.Outreach.linkedin_toast import ToastIsResendCoolDown
from service.Outreach.profile_header import EnsureProfileHeaderView
from service.Outreach.connection_status import DetectConnectionStatus
from service.Outreach.send_invite import ClickSendInvitation
from service.Outreach.visible import ListVisibleActionButtons
from service.Outreach.dismiss_email import DismissEmailGate
from service.Outreach.connection_available import ProfileConnectStillAvailable
from service.Outreach.invite_ui import WaitForInviteUi, TriggerConnect
from service.Outreach.linkedin_outreach import FillAndSendNote, ReadLinkedinToast
from service.Outreach.confirm_withdraw import ConfirmWithdrawDialog
from service.Outreach.confirm_invite import InvitationConfirmed



async def SendConnectionRequest(page: Page, *, note: str | None = None) -> dict[str, Any]:
    log_task("Checking connection status on profile")
    await EnsureProfileHeaderView(page)
    status = await DetectConnectionStatus(page)
    log_task("Connection status detected", status=status)
    if status == "connected":
        log_task("SKIP connect — already connected")
        return {
            "connection_sent": False,
            "already_connected": True,
            "connection_status": "connected",
            "note_sent": False,
            "details": {"reason": "already_connected"},
        }
    if status == "pending":
        # Do NOT withdraw+resend: LinkedIn blocks a new invite for ~3 weeks after withdraw.
        # Notes must be included on the first invitation.
        if note and (note or "").strip():
            log_task(
                "SKIP note — invitation already pending; LinkedIn cannot add a note later "
                "(withdraw+resend is blocked for ~3 weeks)"
            )
            return {
                "connection_sent": False,
                "already_connected": False,
                "connection_status": "pending",
                "note_sent": False,
                "error": (
                    "Invitation already pending without a note. LinkedIn does not allow "
                    "editing the note, and withdrawing then resending is blocked for about "
                    "3 weeks. Use connection_note on the first invite next time."
                ),
                "details": {"reason": "pending_note_unavailable"},
            }
        log_task("SKIP connect — invitation already pending")
        return {
            "connection_sent": False,
            "already_connected": False,
            "connection_status": "pending",
            "note_sent": False,
            "details": {"reason": "invitation_already_pending"},
        }

    log_task("START connect — opening invite UI")
    ui_state = await TriggerConnect(page)
    log_task("Invite UI state after connect click", state=ui_state)

    if ui_state == "pending":
        log_task("DONE connect — already pending after click")
        return {
            "connection_sent": True,
            "already_connected": False,
            "connection_status": "pending",
            "note_sent": False,
            "details": {"mode": "instant_pending", "confirmed_via": "pending_button"},
        }

    if ui_state == "none" or ui_state == "menu":
        toast = await ReadLinkedinToast(page)
        buttons = await ListVisibleActionButtons(page)
        await DumpConnectDom(page)
        screenshot = await SaveDebugScreenshot(page, "connect_no_modal")
        if ToastIsResendCoolDown(toast):
            log_task("FAILED connect — LinkedIn resend cooldown", toast=toast[:160])
            return {
                "connection_sent": False,
                "already_connected": False,
                "connection_status": status,
                "note_sent": False,
                "error": toast
                or (
                    "LinkedIn blocks resending an invitation for about 3 weeks after "
                    "withdrawing the previous one."
                ),
                "details": {
                    "mode": "failed",
                    "reason": "resend_cooldown",
                    "toast": toast,
                    "screenshot": screenshot,
                    "status_before": status,
                },
            }
        log_task(
            "FAILED connect — invite UI never opened",
            state=ui_state,
            buttons=", ".join(buttons[:12]) or "none",
            screenshot=screenshot,
            toast=(toast[:120] if toast else None),
        )
        return {
            "connection_sent": False,
            "already_connected": False,
            "connection_status": status,
            "note_sent": False,
            "error": (
                (toast + " — ") if toast else ""
            )
            + (
                "Invite modal did not open after Connect "
                f"(ui_state={ui_state}). On Premium/Follow profiles, Connect is under More — "
                "check .cache/outreach_debug/"
            ),
            "details": {
                "mode": "failed",
                "ui_state": ui_state,
                "visible_buttons": buttons[:15],
                "screenshot": screenshot,
                "toast": toast or None,
                "status_before": status,
            },
        }
    if not await InviteDialogIsReal(page) and ui_state not in {"invite_controls", "pending"}:
        screenshot = await SaveDebugScreenshot(page, "connect_wrongDialogue")
        log_task("FAILED connect — dialog is not invite modal", screenshot=screenshot, state=ui_state)
        return {
            "connection_sent": False,
            "already_connected": False,
            "connection_status": status,
            "note_sent": False,
            "error": "Opened UI that is not the connection invite modal",
            "details": {"mode": "failed", "screenshot": screenshot, "ui_state": ui_state},
        }
    await HandleHowDoYouKnow(page)
    await DismissEmailGate(page)
    if await InviteDialogIsReal(page) or ui_state in {"dialog", "invite_controls"}:
        log_task("Invite modal ready")
    note_sent = False
    sent = False
    if note:
        # Wait briefly for Premium modal buttons to settle
        await WaitForInviteUi(page, timeout_ms=4000, accept_menu=False)
        log_task("START note — filling connection note", chars=len(note))
        note_sent = await FillAndSendNote(page, note)
        if note_sent:
            log_task("Send clicked after note")
            sent = True
        else:
            log_task("Note flow incomplete — trying send without note")
    if not sent:
        log_task("Sending invitation without note")
        sent = await ClickSendInvitation(page)
    await asyncio.sleep(1.5)
    await DismissEmailGate(page)

    # Reload profile and re-check — do not trust Send click alone
    try:
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.3)
    except Exception:
        pass
    try:
        await page.reload(wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2.0)
    except Exception as exc:
        log_task("Profile reload after send failed", error=str(exc)[:80])
    await EnsureProfileHeaderView(page)

    confirmed = await InvitationConfirmed(page)
    if confirmed:
        log_task("DONE connect — invitation confirmed (Pending)")
        return {
            "connection_sent": True,
            "already_connected": False,
            "connection_status": "pending",
            "note_sent": bool(note_sent),
            "details": {
                "mode": "connect_with_note" if note_sent else "connect_without_note",
                "confirmed_via": "pending_after_reload",
            },
        }

    # Send click without Pending after reload = false positive
    screenshot = await SaveDebugScreenshot(page, "connect_not_pending_after_send")
    still_connect = await ProfileConnectStillAvailable(page)
    log_task(
        "FAILED connect — Send clicked but Pending not confirmed after reload",
        still_connect=still_connect,
        send_clicked=bool(sent or note_sent),
        screenshot=screenshot,
    )
    return {
        "connection_sent": False,
        "already_connected": False,
        "connection_status": "not_connected" if still_connect else status,
        "note_sent": False,
        "error": (
            "Invite UI was used but LinkedIn did not show Pending after reload. "
            "Check .cache/outreach_debug/connect_not_pending_after_send.png"
        ),
        "details": {
            "mode": "failed",
            "send_clicked": bool(sent or note_sent),
            "note_attempted": bool(note_sent),
            "invite_still_available": still_connect,
            "screenshot": screenshot,
            "status_before": status,
        },
    }
