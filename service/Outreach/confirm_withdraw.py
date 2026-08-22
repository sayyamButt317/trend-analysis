import asyncio
from playwright.async_api import Page
from service.Outreach.visible import ClickFirst


async def ConfirmWithdrawDialog(page: Page) -> bool:
    await asyncio.sleep(0.7)
    confirmed = await ClickFirst(
        page,
        [
            'div[role="dialog"] button.artdeco-button--primary:has-text("Withdraw")',
            'div[role="alertdialog"] button.artdeco-button--primary:has-text("Withdraw")',
            'div[role="dialog"] button:text-is("Withdraw")',
            'div[role="alertdialog"] button:text-is("Withdraw")',
            'button.artdeco-button--primary:text-is("Withdraw")',
        ],
        timeout=3500,
    )
    if confirmed:
        return True
    return bool(
        await page.evaluate(
            r"""() => {
                const dialogs = Array.from(document.querySelectorAll(
                    'div[role="dialog"], div[role="alertdialog"], div.artdeco-modal'
                )).filter(d => {
                    const r = d.getBoundingClientRect();
                    const style = window.getComputedStyle(d);
                    return r.width > 40 && r.height > 40
                        && style.display !== 'none' && style.visibility !== 'hidden';
                });
                for (const dlg of dialogs) {
                    const text = (dlg.innerText || '').toLowerCase();
                    if (!text.includes('withdraw')) continue;
                    const btn = Array.from(dlg.querySelectorAll('button')).find(b => {
                        const t = ((b.innerText || '') + ' ' + (b.getAttribute('aria-label') || '')).toLowerCase().trim();
                        return t === 'withdraw' || t.includes('withdraw invitation');
                    });
                    if (btn) { btn.click(); return true; }
                }
                return false;
            }"""
        )
    )