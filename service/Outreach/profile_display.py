from __future__ import annotations
from playwright.async_api import Page


async def ProfilePersonName(page: Page) -> str:
    try:
        name = await page.evaluate(
            r"""() => {
                const pick = (el) => {
                    if (!el) return '';
                    const t = (el.innerText || el.textContent || '').trim().split('\n')[0].trim();
                    return t.slice(0, 120);
                };
                for (const sel of [
                    'main h1',
                    'h1.text-heading-xlarge',
                    'section.artdeco-card h1',
                    '.pv-text-details__left-panel h1',
                    'h1',
                    '.text-heading-xlarge',
                ]) {
                    const el = document.querySelector(sel);
                    const t = pick(el);
                    if (t && t.length > 1) return t;
                }
                const title = (document.title || '').trim();
                const titleMatch = title.match(/^(.+?)\s*\|\s*LinkedIn/i);
                if (titleMatch && titleMatch[1].trim().length > 1) {
                    return titleMatch[1].trim().slice(0, 120);
                }
                const invites = Array.from(document.querySelectorAll(
                    'button[aria-label], a[aria-label], [role="button"][aria-label]'
                ))
                    .map(el => {
                        const aria = el.getAttribute('aria-label') || '';
                        const m = aria.match(/invite\s+(.+?)\s+to\s+connect/i);
                        if (!m) return null;
                        const r = el.getBoundingClientRect();
                        if (r.width < 2 || r.top < 40 || r.top > 520) return null;
                        return { name: m[1].trim(), top: r.top, left: r.left };
                    })
                    .filter(Boolean)
                    .sort((a, b) => a.top - b.top || a.left - b.left);
                return invites.length ? invites[0].name : '';
            }"""
        )
        return (name or "").strip()[:120]
    except Exception:
        return ""
