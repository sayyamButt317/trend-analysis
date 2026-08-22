from playwright.async_api import Page

from service.Outreach.profile_display import ProfilePersonName

async def ProfileConnectStillAvailable(page: Page) -> bool:
    """True if Invite {profile} to connect is still a visible header/menu CTA."""
    profile_name = await ProfilePersonName(page)
    if not profile_name:
        return False
    try:
        return bool(
            await page.evaluate(
                r"""(profileName) => {
                    const tokens = (profileName || '').split(/\s+/).filter(t => t.length > 1);
                    if (!tokens.length) return false;
                    const nodes = Array.from(document.querySelectorAll('button, a, [role="button"]'));
                    return nodes.some(el => {
                        const aria = (el.getAttribute('aria-label') || '');
                        if (!/invite/i.test(aria) || !/connect/i.test(aria)) return false;
                        if (!tokens.every(t => new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i').test(aria))) return false;
                        const style = window.getComputedStyle(el);
                        const r = el.getBoundingClientRect();
                        if (style.display === 'none' || style.visibility === 'hidden') return false;
                        // Must be on-screen in the header band (not offscreen sidebar virtual list)
                        return r.width > 2 && r.height > 2 && r.top > 40 && r.top < 560;
                    });
                }""",
                profile_name,
            )
        )
    except Exception:
        return False