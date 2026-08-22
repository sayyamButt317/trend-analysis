from __future__ import annotations
from playwright.async_api import Page
from service.Outreach.linkedin_outreach import ClickFirst

async def ClickWithdrawControl(page: Page) -> bool:
    selectors = [
        'div[role="dialog"] button:text-is("Withdraw")',
        'div[role="alertdialog"] button:text-is("Withdraw")',
        'div[role="dialog"] button.artdeco-button--primary:has-text("Withdraw")',
        '[role="menuitem"]:text-is("Withdraw")',
        '[role="menuitem"]:has-text("Withdraw invitation")',
        '[role="menuitem"]:has-text("Withdraw")',
        'div[role="menu"] button:has-text("Withdraw")',
        'div.artdeco-dropdown__content button:has-text("Withdraw")',
        'div.artdeco-dropdown__item:has-text("Withdraw")',
        'button:text-is("Withdraw invitation")',
        'button:has-text("Withdraw invitation")',
        'button.artdeco-button--primary:has-text("Withdraw")',
        'button:text-is("Withdraw")',
    ]
    if await ClickFirst(page, selectors, timeout=3500):
        return True
    return bool(
        await page.evaluate(
            r"""() => {
                const nodes = Array.from(document.querySelectorAll(
                    'button, [role="menuitem"], [role="option"], div[role="menu"] *, .artdeco-dropdown__item, li'
                ));
                const hit = nodes.find(b => {
                    const t = ((b.innerText || '') + ' ' + (b.getAttribute('aria-label') || '')).toLowerCase().trim();
                    const r = b.getBoundingClientRect();
                    if (r.width < 2 || r.height < 2) return false;
                    if (t.includes('cancel') || t.includes('keep')) return false;
                    return t === 'withdraw' || t.includes('withdraw invitation') || t === 'withdraw invite';
                });
                if (!hit) return false;
                hit.click();
                return true;
            }"""
        )
    )
