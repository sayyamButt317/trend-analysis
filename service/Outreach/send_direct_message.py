
import asyncio
from typing import Any
from agents.outreach.pipeline_log import log_task
from service.Outreach.constants import MESSAGE_BUTTON_SELECTORS
from playwright.async_api import Page
from service.Outreach.visible_button import FirstVisible, ClickFirst
from service.Outreach.profile_card import ProfileRoot


async def send_direct_message(page: Page, message: str) -> dict[str, Any]:
    if not (message or "").strip():
        log_task("SKIP message — empty body")
        return {"message_sent": False, "error": "message is empty"}

    log_task("START message — opening Message composer")
    root = await ProfileRoot(page)
    opened = await ClickFirst(page, MESSAGE_BUTTON_SELECTORS, timeout=3000, root=root)
    if not opened:
        opened = await ClickFirst(page, MESSAGE_BUTTON_SELECTORS, timeout=2500)
    if not opened:
        log_task("FAILED message — Message button not found")
        return {
            "message_sent": False,
            "error": "Message button not found (may require an existing connection)",
        }

    await asyncio.sleep(1.2)
    editor = await FirstVisible(
        page,
        [
            'div.msg-form__contenteditable[contenteditable="true"]',
            'div[role="textbox"][contenteditable="true"]',
            'div.msg-form__msg-content-container div[contenteditable="true"]',
            'textarea[name="message"]',
            "textarea",
        ],
        timeout=5000,
    )
    if not editor:
        log_task("FAILED message — composer not found")
        return {"message_sent": False, "error": "Message composer not found"}

    log_task("Typing message", chars=len(message.strip()))
    try:
        await editor.click()
        await editor.fill("")
        await editor.type(message.strip(), delay=20)
    except Exception:
        await page.keyboard.type(message.strip(), delay=20)

    await asyncio.sleep(0.5)
    sent = await ClickFirst(
        page,
        [
            "button.msg-form__send-button",
            'button:has-text("Send")',
            'button[type="submit"]:has-text("Send")',
        ],
        timeout=3000,
    )
    if not sent:
        await page.keyboard.press("Control+Enter")
        sent = True

    await asyncio.sleep(1.0)
    if sent:
        log_task("DONE message — sent")
    else:
        log_task("FAILED message — could not click Send")
    return {
        "message_sent": bool(sent),
        "error": None if sent else "Could not click Send in message composer",
        "details": {"preview": message.strip()[:120]},
    }
