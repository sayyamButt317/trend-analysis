import asyncio
from agents.outreach.pipeline_log import log_task
from playwright.async_api import Page
from service.Outreach.click_send import ClickSendWithNote
from service.Outreach.connect_debugging import SaveDebugScreenshot
from service.Outreach.visible_button import ClickFirst, FirstVisible



async def FillAndSendNote(page: Page, note: str) -> bool:
    if not (note or "").strip():
        return False
    note = note.strip()[:300]
    textarea_selectors = [
        'textarea[name="message"]',
        "textarea#custom-message",
        "textarea.connect-button-send-invite__custom-message",
        'div[role="dialog"] textarea',
        'div[role="alertdialog"] textarea',
        "div.artdeco-modal textarea",
        'textarea[placeholder*="note" i]',
        "textarea",
    ]
    textarea = await FirstVisible(page, textarea_selectors, timeout=1500)
    if not textarea:
        log_task("Clicking Add a note")
        add_note = await ClickFirst(
            page,
            [
                'button:text-is("Add a note")',
                'button:has-text("Add a note")',
                'button[aria-label*="Add a note" i]',
                'button:has-text("Add note")',
            ],
            timeout=4000,
        )
        if not add_note:
            add_note = bool(
                await page.evaluate(
                    r"""() => {
                        const btns = Array.from(document.querySelectorAll('button'));
                        const hit = btns.find(b => {
                            const t = ((b.innerText || '') + ' ' + (b.getAttribute('aria-label') || '')).toLowerCase().trim();
                            const r = b.getBoundingClientRect();
                            if (r.width < 2 || r.height < 2) return false;
                            return t === 'add a note' || t === 'add note';
                        });
                        if (!hit) return false;
                        hit.click();
                        return true;
                    }"""
                )
            )
        if not add_note:
            log_task("Add a note button not found")
            await SaveDebugScreenshot(page, "note_add_button_missing")
            return False
        await asyncio.sleep(0.9)
        textarea = await FirstVisible(page, textarea_selectors, timeout=6000)
    if not textarea:
        log_task("Note textarea not found")
        await SaveDebugScreenshot(page, "note_textarea_missing")
        return False
    log_task("Typing connection note", chars=len(note))
    try:
        await textarea.click(timeout=3000)
        await textarea.fill("")
        await textarea.fill(note)
    except Exception:
        try:
            await textarea.click()
            await page.keyboard.type(note, delay=12)
        except Exception as exc:
            log_task("Typing note failed", error=str(exc)[:80])
            return False
    await asyncio.sleep(0.6)
    if await ClickSendWithNote(page):
        return True
    log_task("Send after note not clicked")
    await SaveDebugScreenshot(page, "note_send_missing")
    return False
