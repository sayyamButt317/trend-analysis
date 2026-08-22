from __future__ import annotations
import asyncio
import logging
import re
from pathlib import Path
from typing import Any
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from agents.outreach.pipeline_log import log_task
from service.AnalyzeUserLinkedIn.safety import linkedin_human_delay
from service.AnalyzeUserLinkedIn.session import LinkedInPlaywrightSession, run_linkedin_playwright
from service.Outreach.connection_status import DetectConnectionStatus
from service.Outreach.constants import DEBUG_DIR
from service.Outreach.send_connectionrequest import send_connection_request
from service.Outreach.send_direct_message import send_direct_message

logger = logging.getLogger(__name__)



async def run_linkedin_outreach(
    *,
    profile_url: str,
    connection_note: str = "",
    message: str = "",
    send_connection: bool = True,
    send_message: bool = True,
    headless: bool = True,
) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        result: dict[str, Any] = {
            "profile_url": profile_url,
            "profile_opened": False,
            "connection_status": "unknown",
            "connection_sent": False,
            "note_sent": False,
            "message_sent": False,
            "already_connected": False,
            "error": None,
            "details": {},
            "logs": [],
        }

        session = LinkedInPlaywrightSession(headless=headless)
        try:
            log_task("START login — launching Playwright LinkedIn session", headless=headless)
            await session.start()
            result["logs"].append("linkedin_session_started")
            log_task("DONE login — LinkedIn session ready")

            log_task("START open profile", url=profile_url)
            opened = await session.navigate(profile_url, purpose="outreach_profile")
            result["profile_opened"] = bool(opened)
            if not opened:
                result["error"] = f"Failed to open profile: {profile_url}"
                log_task("FAILED open profile", url=profile_url)
                return result
            log_task("DONE open profile", url=profile_url)

            await linkedin_human_delay(session.safety)
            status = await DetectConnectionStatus(session.page)
            # Premium action-row Pending can appear a beat after Follow/Message
            if status == "not_connected":
                await asyncio.sleep(1.4)
                status = await DetectConnectionStatus(session.page)
            result["connection_status"] = status
            result["already_connected"] = status == "connected"
            result["logs"].append(f"status={status}")
            log_task("Profile status checked", status=status)

            wants_note = bool((connection_note or "").strip())
            should_connect = send_connection and status not in {"connected", "pending"}
            if should_connect:
                connect_result = await send_connection_request(
                    session.page,
                    note=connection_note or None,
                )
                result.update(
                    {
                        "connection_sent": connect_result.get("connection_sent", False),
                        "note_sent": connect_result.get("note_sent", False),
                        "already_connected": connect_result.get("already_connected", False),
                        "connection_status": connect_result.get("connection_status")
                        or result["connection_status"],
                    }
                )
                if connect_result.get("error"):
                    result["error"] = connect_result["error"]
                result["details"]["connection"] = connect_result.get("details") or {}
                result["logs"].append(
                    f"connection_sent={result['connection_sent']} note_sent={result['note_sent']}"
                )
                await linkedin_human_delay(session.safety)
            elif send_connection and status == "pending" and wants_note:
                tip = (
                    "Invitation already pending — LinkedIn cannot add a note after send, "
                    "and withdraw+resend is blocked for ~3 weeks. Include connection_note "
                    "on the first invite."
                )
                result["error"] = tip
                result["details"]["connection"] = {"reason": "pending_note_unavailable"}
                result["logs"].append("note_unavailable_already_pending")
                log_task("SKIP connect/note — already pending", reason="pending_note_unavailable")
            elif send_connection:
                log_task(
                    "SKIP connect step",
                    reason="already_connected" if status == "connected" else "already_pending",
                )
            else:
                log_task("SKIP connect step", reason="send_connection=false")

            if send_message and message:
                current = await DetectConnectionStatus(session.page)
                result["connection_status"] = current
                if current == "connected" or result["already_connected"]:
                    msg_result = await send_direct_message(session.page, message)
                    result["message_sent"] = bool(msg_result.get("message_sent"))
                    if msg_result.get("error") and not result["error"]:
                        result["error"] = msg_result["error"]
                    result["details"]["message"] = msg_result.get("details") or {}
                    result["logs"].append(f"message_sent={result['message_sent']}")
                else:
                    if result.get("note_sent") and connection_note:
                        result["logs"].append("message_skipped_used_connection_note")
                        log_task("SKIP DM — connection note already used as outreach message")
                    else:
                        tip = (
                            "Not connected yet — LinkedIn usually blocks DMs until accepted. "
                            "Use connection_note to include a note with the invite."
                        )
                        result["details"]["message"] = {"skipped": True, "reason": tip}
                        if send_message and not result.get("note_sent"):
                            result["logs"].append("message_skipped_not_connected")
                        log_task("SKIP DM — not connected yet")
            elif send_message:
                log_task("SKIP message", reason="empty_message")
            else:
                log_task("SKIP message", reason="send_message=false")

            log_task(
                "Playwright outreach actions finished",
                connection_sent=result["connection_sent"],
                note_sent=result["note_sent"],
                message_sent=result["message_sent"],
            )
            return result
        except Exception as exc:
            logger.exception("LinkedIn outreach failed for %s", profile_url)
            log_task("FAILED outreach run", error=str(exc)[:160])
            result["error"] = str(exc)
            return result
        finally:
            log_task("Closing browser session")
            await session.close(save_session=result.get("error") is None)
            log_task("DONE — browser closed")

    return await run_linkedin_playwright(_run)


def extract_username_from_url(url: str) -> str | None:
    match = re.search(r"linkedin\.com/in/([A-Za-z0-9_-]+)", url or "", re.I)
    return match.group(1) if match else None
