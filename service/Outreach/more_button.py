import re
from playwright.async_api import Page

async def FindHeaderMoreButton(page: Page):
    candidates = [
        page.get_by_role("button", name=re.compile(r"^\s*More\s*$", re.I)),
        page.get_by_role("button", name=re.compile(r"more actions", re.I)),
        page.locator('button[aria-label*="More actions" i]'),
        page.locator('main button:text-is("More")'),
    ]
    best = None
    best_score = -1
    for loc in candidates:
        try:
            count = await loc.count()
        except Exception:
            continue
        for i in range(min(count, 6)):
            item = loc.nth(i)
            try:
                if not await item.is_visible():
                    continue
                box = await item.bounding_box()
                if not box:
                    continue
                if box["y"] < 40 or box["y"] > 520:
                    continue
                # Prefer More on the right side of the main column (action row)
                score = 100 - abs(box["y"] - 200) / 10 + (box["x"] / 50)
                if score > best_score:
                    best_score = score
                    best = item
            except Exception:
                continue
    return best
