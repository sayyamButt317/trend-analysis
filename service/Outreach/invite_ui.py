import asyncio
from playwright.async_api import Page
from service.Outreach.invite_dialog import InviteDialogIsReal
from service.Outreach.pending_header import PendingHeaderVisible
from service.Outreach.visible import FirstVisible

async def WaitForInviteUi(
    page: Page,
    *,
    timeout_ms: int = 10000,
    accept_menu: bool = True,
) -> str:
    """Wait for invite modal. If accept_menu=False, ignore open More dropdowns."""
    deadline = asyncio.get_event_loop().time() + (timeout_ms / 1000)
    while asyncio.get_event_loop().time() < deadline:
        try:
            kind = await page.evaluate(
                r"""() => {
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== 'none' && style.visibility !== 'hidden'
                            && Number(style.opacity) !== 0 && rect.width > 40 && rect.height > 40;
                    };
                    const nodes = Array.from(document.querySelectorAll(
                        'div[role="dialog"], div[role="alertdialog"], div.artdeco-modal, div.send-invite, div.artdeco-modal-overlay, .artdeco-modal__content'
                    ));
                    for (const dlg of nodes) {
                        if (!visible(dlg)) continue;
                        const t = (dlg.innerText || '').toLowerCase();
                        if (t.includes('add a note') || t.includes('send without a note')
                            || t.includes('invitation') || t.includes('how do you know')
                            || !!dlg.querySelector('textarea[name="message"], textarea#custom-message'))
                            return 'dialog';
                    }
                    const inviteBtn = Array.from(document.querySelectorAll('button')).some(b => {
                        const t = ((b.innerText || '') + ' ' + (b.getAttribute('aria-label') || '')).toLowerCase().trim();
                        const r = b.getBoundingClientRect();
                        if (r.width < 2 || r.height < 2) return false;
                        return t === 'add a note' || t.includes('send without a note') || t.includes('send invitation');
                    });
                    if (inviteBtn) return 'invite_controls';

                    const h1 = document.querySelector('main h1');
                    const header = h1 && (h1.closest('section') || h1.closest('.artdeco-card'));
                    if (header) {
                        const pending = Array.from(header.querySelectorAll('button, a')).some(el => {
                            const text = (el.innerText || '').trim();
                            const aria = el.getAttribute('aria-label') || '';
                            return /^\s*pending\s*$/i.test(text) || /pending/i.test(aria);
                        });
                        if (pending) return 'pending';
                    }
                    if (document.querySelector('div[role="menu"], div.artdeco-dropdown__content--is-open, [role="menuitem"]'))
                        return 'menu';
                    return null;
                }"""
            )
            if kind == "menu" and not accept_menu:
                kind = None
            if kind:
                return kind
        except Exception:
            pass

        if await PendingHeaderVisible(page):
            return "pending"
        if await InviteDialogIsReal(page):
            return "dialog"
        if await FirstVisible(
            page,
            [
                'button:text-is("Send without a note")',
                'button:has-text("Send without a note")',
                'button:text-is("Add a note")',
                'button:has-text("Add a note")',
                'h2:has-text("Add a note to your invitation")',
                'h2:has-text("invitation")',
            ],
            timeout=200,
        ):
            return "invite_controls"
        if accept_menu and await FirstVisible(
            page,
            [
                'div[role="menu"]',
                "div.artdeco-dropdown__content--is-open",
                "div.artdeco-dropdown__content:visible",
                '[role="menuitem"]',
            ],
            timeout=150,
        ):
            return "menu"
        await asyncio.sleep(0.25)
    return "none"
