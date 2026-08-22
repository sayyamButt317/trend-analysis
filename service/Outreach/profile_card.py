from playwright.async_api import Page

async def ProfileRoot(page: Page):
    """Top profile intro card only (excludes right-rail 'More profiles for you')."""
    try:
        card = page.locator("main section.artdeco-card").filter(has=page.locator("h1")).first
        if await card.count() > 0:
            return card
    except Exception:
        pass
    for selector in (
        "main section:has(h1)",
        "main div.ph5:has(h1)",
        "main section.artdeco-card",
        "main div.ph5",
    ):
        loc = page.locator(selector).first
        try:
            if await loc.count() > 0:
                return loc
        except Exception:
            continue
    # Last resort: h1's ancestor section — never bare main (sidebar lives there too)
    try:
        h1 = page.locator("main h1").first
        if await h1.count() > 0:
            section = h1.locator("xpath=ancestor::section[1]")
            if await section.count() > 0:
                return section
    except Exception:
        pass
    return page.locator("main h1").first