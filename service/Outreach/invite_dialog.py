from playwright.async_api import Page

async def InviteDialogIsReal(page: Page) -> bool:
    """True when a VISIBLE connection-invite modal is open (skip hidden leftovers)."""
    try:
        return bool(
            await page.evaluate(
                r"""() => {
                    const nodes = Array.from(document.querySelectorAll(
                        'div[role="dialog"], div[role="alertdialog"], div.artdeco-modal, div.send-invite, div.artdeco-modal-overlay, .artdeco-modal__content'
                    ));
                    for (const dlg of nodes) {
                        const style = window.getComputedStyle(dlg);
                        if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) continue;
                        const rect = dlg.getBoundingClientRect();
                        if (rect.width < 40 || rect.height < 40) continue;
                        const t = (dlg.innerText || '').toLowerCase();
                        if (t.includes('add a note') || t.includes('send without a note')
                            || t.includes('invitation') || t.includes('how do you know')
                            || !!dlg.querySelector('textarea[name="message"], textarea#custom-message'))
                            return true;
                    }
                    return Array.from(document.querySelectorAll('button')).some(b => {
                        const t = ((b.innerText || '') + ' ' + (b.getAttribute('aria-label') || '')).toLowerCase().trim();
                        const r = b.getBoundingClientRect();
                        if (r.width < 2 || r.height < 2) return false;
                        return t === 'add a note' || t.includes('send without a note') || t.includes('send invitation');
                    });
                }"""
            )
        )
    except Exception:
        return False
