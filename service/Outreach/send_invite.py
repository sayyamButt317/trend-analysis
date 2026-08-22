from playwright.async_api import Page
from service.Outreach.constants import INVITE_DIALOG
from service.Outreach.visible import ClickFirst


async def ClickSendInvitation(page: Page) -> bool:
    """Click Send when sending without a note."""
    selectors = [
        'button[aria-label*="Send invitation" i]',
        'button[aria-label*="Send now" i]',
        'button:has-text("Send invitation")',
        'button:text-is("Send without a note")',
        'button:has-text("Send without a note")',
        'button.artdeco-button--primary:has-text("Send")',
    ]
    root = page.locator(INVITE_DIALOG).first
    if await ClickFirst(page, selectors, timeout=2500, root=root):
        return True
    if await ClickFirst(
        page,
        [
            'button:text-is("Send without a note")',
            'button:has-text("Send without a note")',
            'button:text-is("Send invitation")',
            'button[aria-label*="Send invitation" i]',
        ],
        timeout=3000,
    ):
        return True
    return bool(
        await page.evaluate(
            r"""() => {
                const btns = Array.from(document.querySelectorAll('button'));
                const hit = btns.find(b => {
                    const t = ((b.innerText||'') + ' ' + (b.getAttribute('aria-label')||'')).toLowerCase();
                    const r = b.getBoundingClientRect();
                    if (r.width < 2 || r.height < 2) return false;
                    return t.includes('send without a note')
                        || t.includes('send invitation')
                        || t.includes('send now');
                });
                if (!hit) return false;
                hit.click();
                return true;
            }"""
        )
    )

