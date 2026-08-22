import asyncio
import re
from playwright.async_api import Page

from agents.outreach.pipeline_log import log_task
from service.Outreach.human_click import HumanClickLocator

async def ClickConnectInOpenMenu(page: Page, profile_name: str = "") -> bool:
    """Click Connect inside an open More / overflow dropdown."""
    menu_roots = [
        page.locator("div.artdeco-dropdown__content--is-open").last,
        page.locator('div[role="menu"]').last,
        page.locator("div.artdeco-dropdown__content:visible").last,
        page.locator(".artdeco-dropdown__content-inner").last,
    ]
    menu = None
    for root in menu_roots:
        try:
            await root.wait_for(state="visible", timeout=2000)
            menu = root
            break
        except Exception:
            continue

    # Prefer the dropdown row itself (not a nested span) — Ember needs the item click
    item_selectors = []
    if profile_name:
        item_selectors.append(f'[aria-label="Invite {profile_name} to connect"]')
        item_selectors.append(
            f'div.artdeco-dropdown__item:has-text("{profile_name}")'
        )
    item_selectors.extend(
        [
            'div.artdeco-dropdown__item:text-is("Connect")',
            '[role="menuitem"]:text-is("Connect")',
            'div.artdeco-dropdown__item >> text=/^\\s*Connect\\s*$/',
            'div[role="menu"] div.artdeco-dropdown__item:has-text("Connect")',
            'div.artdeco-dropdown__content--is-open div.artdeco-dropdown__item:has-text("Connect")',
        ]
    )

    for sel in item_selectors:
        try:
            scope = menu if menu is not None else page
            loc = scope.locator(sel).first
            try:
                await loc.wait_for(state="visible", timeout=1500)
            except Exception:
                if await loc.count() == 0:
                    continue
            if await loc.count() == 0:
                continue
            label = ""
            try:
                label = ((await loc.inner_text()) or (await loc.get_attribute("aria-label")) or "Connect")
            except Exception:
                label = "Connect"
            if re.search(r"connections", label, re.I):
                continue
            first_line = re.sub(r"\s+", " ", label).strip().split("\n")[0].strip()
            ok_label = bool(
                re.match(r"^\s*connect\s*$", first_line, re.I)
                or (profile_name and re.search(r"invite", first_line, re.I) and re.search(r"connect", first_line, re.I))
            )
            if not ok_label:
                continue
            log_task("Clicking Connect in More menu", label=first_line[:80])
            if await HumanClickLocator(page, loc):
                await asyncio.sleep(0.4)
                return True
            try:
                await loc.click(timeout=3000, force=True, delay=80)
                return True
            except Exception:
                continue
        except Exception:
            continue

    return bool(
        await page.evaluate(
            r"""() => {
                const roots = [
                    ...document.querySelectorAll('div.artdeco-dropdown__content--is-open'),
                    ...document.querySelectorAll('div[role="menu"]'),
                    ...document.querySelectorAll('div.artdeco-dropdown__content'),
                ];
                const scope = roots[0] || document;
                const items = Array.from(scope.querySelectorAll(
                    'div.artdeco-dropdown__item, [role="menuitem"], button, div[role="button"]'
                ));
                for (const el of items) {
                    const text = (el.innerText || '').trim().split('\n')[0].trim();
                    const aria = (el.getAttribute('aria-label') || '');
                    if (/connections/i.test(text + ' ' + aria)) continue;
                    if (!/^connect$/i.test(text) && !( /invite/i.test(aria) && /connect/i.test(aria) )) continue;
                    el.scrollIntoView({ block: 'nearest' });
                    el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));
                    el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
                    el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
                    el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                    el.click();
                    return true;
                }
                return false;
            }"""
        )
    )