from playwright.async_api import Page
from agents.outreach.pipeline_log import log_task
from service.Outreach.human_click import HumanClickLocator



async def ClickSendWithNote(page: Page) -> bool:
    selectors = [
        'button[aria-label*="Send invitation" i]',
        'button[aria-label*="Send now" i]',
        'button:text-is("Send invitation")',
        'button:has-text("Send invitation")',
        'button.artdeco-button--primary:text-is("Send")',
        'button:text-is("Send")',
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.count() == 0 or not await loc.is_visible():
                continue
            label = ((await loc.inner_text()) or (await loc.get_attribute("aria-label")) or "").lower()
            if "without a note" in label:
                continue
            log_task("Clicking Send with note", label=(label.strip()[:60] or sel))
            if await HumanClickLocator(page, loc):
                return True
        except Exception:
            continue
    return bool(
        await page.evaluate(
            r"""() => {
                const btns = Array.from(document.querySelectorAll('button'));
                const hit = btns.find(b => {
                    const t = ((b.innerText || '') + ' ' + (b.getAttribute('aria-label') || '')).toLowerCase().trim();
                    const r = b.getBoundingClientRect();
                    if (r.width < 2 || r.height < 2) return false;
                    if (t.includes('without a note')) return false;
                    return t === 'send' || t.includes('send invitation') || t.includes('send now');
                });
                if (!hit) return false;
                hit.click();
                return true;
            }"""
        )
    )
