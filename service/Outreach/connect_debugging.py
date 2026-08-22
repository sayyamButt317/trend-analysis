from playwright.async_api import Page
from agents.outreach.pipeline_log import log_task
from service.Outreach.linkedin_outreach import DEBUG_DIR

async def DumpConnectDom(page: Page) -> str | None:
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        path = DEBUG_DIR / "dom_probe.json"
        info = await page.evaluate(
            """() => {
                const h1s = Array.from(document.querySelectorAll('h1')).map(h => (h.innerText||'').trim().slice(0,80));
                const invites = Array.from(document.querySelectorAll('button, a, [role="button"], .artdeco-button'))
                    .map(el => ({
                        aria: el.getAttribute('aria-label') || '',
                        text: (el.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 40),
                        top: Math.round(el.getBoundingClientRect().top),
                        left: Math.round(el.getBoundingClientRect().left),
                        tag: el.tagName,
                    }))
                    .filter(x => /connect|message|^more$/i.test(x.aria + ' ' + x.text))
                    .slice(0, 40);
                return {
                    url: location.href,
                    title: document.title,
                    hasMain: !!document.querySelector('main'),
                    mainH1: (document.querySelector('main h1')||{}).innerText || null,
                    anyH1: (document.querySelector('h1')||{}).innerText || null,
                    h1s,
                    invites,
                };
            }"""
        )
        path.write_text(__import__('json').dumps(info, indent=2), encoding='utf-8')
        log_task("Saved DOM probe", path=str(path), h1s=len(info.get('h1s') or []), invites=len(info.get('invites') or []))
        return str(path)
    except Exception as exc:
        log_task("DOM probe failed", error=str(exc)[:80])
        return None


async def SaveDebugScreenshot(page: Page, label: str) -> str | None:
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        path = DEBUG_DIR / f"{label}.png"
        await page.screenshot(path=str(path), full_page=False)
        log_task("Saved debug screenshot", path=str(path))
        return str(path)
    except Exception as exc:
        log_task("Could not save debug screenshot", error=str(exc)[:80])
        return None