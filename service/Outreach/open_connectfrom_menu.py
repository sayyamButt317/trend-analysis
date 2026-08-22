import asyncio
from playwright.async_api import Page
from agents.outreach.pipeline_log import log_task
from service.Outreach.click_connect import ClickConnectCoords
from service.Outreach.connect_debugging import SaveDebugScreenshot
from service.Outreach.constants import MORE_BUTTON_SELECTORS
from service.Outreach.human_click import HumanClickLocator
from service.Outreach.menu_connect import ClickConnectInOpenMenu
from service.Outreach.more_button import FindHeaderMoreButton
from service.Outreach.profile_display import ProfilePersonName
from service.Outreach.profile_header import EnsureProfileHeaderView
from service.Outreach.visible import ClickFirst
from service.Outreach.locate_connect import ProfileRoot


async def OpenConnectFromMoreMenu(page: Page) -> bool:
    await EnsureProfileHeaderView(page)
    profile_name = await ProfilePersonName(page)
    log_task("Opening More menu for Connect", profile=profile_name or "unknown")

    more = await FindHeaderMoreButton(page)
    opened = False
    if more:
        opened = await HumanClickLocator(page, more)
    if not opened:
        card = await ProfileRoot(page)
        opened = await ClickFirst(page, MORE_BUTTON_SELECTORS, timeout=2500, root=card)
    if not opened:
        opened = await ClickFirst(page, MORE_BUTTON_SELECTORS, timeout=2000)
    if not opened:
        info = await page.evaluate(
            r"""() => {
                const nodes = Array.from(document.querySelectorAll('button, [role="button"]'));
                const hits = nodes.map(el => {
                    const text = (el.innerText || '').trim().replace(/\s+/g, ' ');
                    const aria = el.getAttribute('aria-label') || '';
                    if (!/^more$/i.test(text) && !/more actions/i.test(aria)) return null;
                    const r = el.getBoundingClientRect();
                    if (r.width < 2 || r.top < 40 || r.top > 520) return null;
                    return { x: r.x + r.width / 2, y: r.y + r.height / 2, left: r.left };
                }).filter(Boolean).sort((a, b) => a.y - b.y || b.left - a.left);
                return hits[0] || null;
            }"""
        )
        if info:
            opened = await ClickConnectCoords(page, info)
    if not opened:
        log_task("More button not found on profile header")
        return False

    await asyncio.sleep(1.0)
    clicked = await ClickConnectInOpenMenu(page, profile_name)
    if clicked:
        return True

    await SaveDebugScreenshot(page, "more_menu_no_connect")
    try:
        labels = await page.evaluate(
            r"""() => {
                const root = document.querySelector(
                    'div[role="menu"], div.artdeco-dropdown__content--is-open, div.artdeco-dropdown__content'
                );
                if (!root) return [];
                return Array.from(root.querySelectorAll('button, [role="menuitem"], div.artdeco-dropdown__item, li, span'))
                    .map(el => (el.innerText || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' '))
                    .filter(t => t && t.length < 80)
                    .slice(0, 20);
            }"""
        )
        log_task("More menu items", items=", ".join(labels) if labels else "none")
    except Exception:
        pass
    return False