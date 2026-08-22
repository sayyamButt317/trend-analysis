import asyncio
from agents.outreach.pipeline_log import log_task
from playwright.async_api import Page
from service.Outreach.connect_button import ResolveHeaderConnectButton
from service.Outreach.human_click import HumanClickLocator
from service.Outreach.locate_connect import FindProfileConnectLocator
from service.Outreach.match_profilelabel import LabelMatchesProfile
from service.Outreach.profile_display import ProfilePersonName

async def ClickConnectCoords(page: Page, info: dict) -> bool:
    try:
        x, y = float(info["x"]), float(info["y"])
        log_task("Mouse click element", x=round(x, 1), y=round(y, 1))
        await page.mouse.move(x, y, steps=12)
        await asyncio.sleep(0.2)
        await page.mouse.click(x, y, delay=60)
        return True
    except Exception as exc:
        log_task("Coord click failed", error=str(exc)[:80])
        return False



async def ClickConnectViaPlayWrightRole(page: Page) -> bool:
    """Click Connect on the profile header with real pointer events."""
    profile_name = await ProfilePersonName(page)
    log_task("Profile person name", name=profile_name or "unknown")

    # Prefer Playwright accessibility locators (pierce more layouts than querySelector)
    locator, loc_label = await FindProfileConnectLocator(page)
    if locator and LabelMatchesProfile(loc_label or "", profile_name):
        log_task("Clicking profile Connect (locator)", label=loc_label)
        if await HumanClickLocator(page, locator):
            return True
        try:
            await locator.focus()
            await page.keyboard.press("Enter")
            return True
        except Exception:
            pass

    info, label = await ResolveHeaderConnectButton(page)
    if info and isinstance(info, dict) and "x" in info:
        log_task("Clicking header Connect (coord)", label=label)
        if await ClickConnectCoords(page, info):
            return True
        if label:
            loc = page.get_by_role("button", name=label).first
            try:
                if await loc.count() > 0:
                    return await HumanClickLocator(page, loc)
            except Exception:
                pass

    if not locator:
        log_task("Profile Connect locator not found", profile=profile_name)
    return 
    

async def ClickElementHandle(page: Page, element) -> bool:
    """Click a DOM element handle with mouse, then Playwright click, then Enter."""
    try:
        await element.scroll_into_view_if_needed()
        await asyncio.sleep(0.3)
        box = await element.bounding_box()
        if box:
            x = box["x"] + box["width"] * 0.5
            y = box["y"] + box["height"] * 0.5
            log_task("Mouse click element", x=round(x, 1), y=round(y, 1))
            await page.mouse.move(x, y, steps=12)
            await asyncio.sleep(0.2)
            await page.mouse.click(x, y, delay=60)
            return True
    except Exception as exc:
        log_task("Element mouse click failed", error=str(exc)[:80])
    try:
        await element.click(timeout=4000, delay=80)
        return True
    except Exception:
        pass
    try:
        await element.focus()
        await page.keyboard.press("Enter")
        return True
    except Exception:
        pass
    try:
        await element.evaluate(
            """el => {
                el.focus();
                el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true }));
                el.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true }));
                el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                el.click();
            }"""
        )
        return True
    except Exception:
        return False


async def JsClickConnectInProfile(page: Page) -> bool:
    """Click Connect inside the h1 profile card only (never sidebar)."""
    profile_name = await ProfilePersonName(page)
    return bool(
        await page.evaluate(
            """(profileName) => {
                const h1 = document.querySelector('main h1');
                if (!h1) return false;
                const name = profileName || (h1.innerText || '').trim().split('\\n')[0].trim();
                const tokens = name.split(/\\s+/).filter(t => t.length > 1);
                const root = h1.closest('section') || h1.closest('.artdeco-card') || h1.parentElement;
                if (!root) return false;
                const isVisible = (el) => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden'
                        && rect.width > 2 && rect.height > 2;
                };
                const isConnectCta = (el) => {
                    const aria = (el.getAttribute('aria-label') || '').trim();
                    const text = (el.innerText || '').trim().replace(/\\s+/g, ' ');
                    if (/connections/i.test(aria + ' ' + text)) return false;
                    if (/invite/i.test(aria) && /connect/i.test(aria)) {
                        if (!tokens.length) return false;
                        return tokens.every(t => new RegExp(t.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&'), 'i').test(aria));
                    }
                    return /^\\+?\\s*connect\\s*$/i.test(text);
                };
                const nodes = Array.from(root.querySelectorAll('button, a, [role="button"], .artdeco-button'));
                for (const el of nodes) {
                    if (!isConnectCta(el)) continue;
                    if (!isVisible(el)) continue;
                    el.scrollIntoView({ block: 'center', inline: 'center' });
                    el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
                    el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
                    el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                    el.click();
                    return true;
                }
                return false;
            }""",
            profile_name,
        )
    )