import re
from playwright.async_api import Page

async def PendingHeaderVisible(page: Page) -> bool:
    """Pending for this profile action row — never sidebar Pending."""
    try:
        # Prefer Playwright — Premium action row often has Pending next to Message
        for role in ("button", "link"):
            loc = page.get_by_role(role, name=re.compile(r"^\s*pending\s*$", re.I))
            try:
                count = await loc.count()
            except Exception:
                count = 0
            for i in range(min(count, 8)):
                item = loc.nth(i)
                try:
                    if not await item.is_visible():
                        continue
                    box = await item.bounding_box()
                    # Premium action row can sit lower; exclude deep-page / sidebar noise
                    if box and 40 < box["y"] < 720 and box["x"] < 1100:
                        return True
                except Exception:
                    continue
        loc = page.locator('main button:text-is("Pending"), main a:text-is("Pending")').first
        if await loc.count() > 0 and await loc.is_visible():
            box = await loc.bounding_box()
            if box and 40 < box["y"] < 720:
                return True
    except Exception:
        pass
    try:
        return bool(
            await page.evaluate(
                r"""() => {
                    const aside = document.querySelector('aside');
                    const asideLeft = aside ? aside.getBoundingClientRect().left : window.innerWidth;
                    const nodes = Array.from(document.querySelectorAll('button, a, [role="button"]'));
                    return nodes.some(el => {
                        if (aside && aside.contains(el)) return false;
                        const text = (el.innerText || '').trim().split('\n')[0].trim();
                        const aria = (el.getAttribute('aria-label') || '');
                        if (!/^\s*pending\s*$/i.test(text) && !/\bpending\b/i.test(aria))
                            return false;
                        const r = el.getBoundingClientRect();
                        // Action-row Pending sits mid/right of main column
                        return r.width > 2 && r.height > 2 && r.top > 40 && r.top < 720
                            && r.left < asideLeft - 8;
                    });
                }"""
            )
        )
    except Exception:
        return False
