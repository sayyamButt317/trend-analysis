import re
from playwright.async_api import Page
from service.Outreach.human_click import HumanClickLocator
from service.Outreach.visible import ClickFirst



async def ClickProfilePendingButton(page: Page) -> bool:

    try:
        loc = page.get_by_role("button", name=re.compile(r"^\s*pending\s*$", re.I))
        count = await loc.count()
        for i in range(min(count, 8)):
            item = loc.nth(i)
            try:
                if not await item.is_visible():
                    continue
                box = await item.bounding_box()
                if not box or box["y"] < 40 or box["y"] > 720 or box["x"] > 1100:
                    continue
                if await HumanClickLocator(page, item):
                    return True
            except Exception:
                continue
    except Exception:
        pass
    clicked = await ClickFirst(
        page,
        [
            'main button:text-is("Pending")',
            'main a:text-is("Pending")',
            'main button:has-text("Pending")',
        ],
        timeout=2500,
    )
    if clicked:
        return True
    return bool(
        await page.evaluate(
            r"""() => {
                const aside = document.querySelector('aside');
                const asideLeft = aside ? aside.getBoundingClientRect().left : window.innerWidth;
                const nodes = Array.from(document.querySelectorAll('button, a, [role="button"]'));
                const hit = nodes.find(el => {
                    if (aside && aside.contains(el)) return false;
                    const text = (el.innerText || '').trim().split('\n')[0].trim();
                    if (!/^\s*pending\s*$/i.test(text)) return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 2 && r.height > 2 && r.top > 40 && r.top < 720
                        && r.left < asideLeft - 8;
                });
                if (!hit) return false;
                hit.click();
                return true;
            }"""
        )
    )
