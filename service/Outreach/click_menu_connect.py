from playwright.async_api import Page

async def JsClickMenuConnect(page: Page) -> bool:
    return bool(
        await page.evaluate(
            r"""() => {
                const roots = [
                    ...document.querySelectorAll('div[role="menu"]'),
                    ...document.querySelectorAll('div.artdeco-dropdown__content--is-open'),
                    ...document.querySelectorAll('div.artdeco-dropdown__content'),
                ];
                const scope = roots.length ? roots[roots.length - 1] : document;
                const items = Array.from(scope.querySelectorAll(
                    '[role="menuitem"], div.artdeco-dropdown__item, div.artdeco-dropdown__content li, div[role="menu"] button, div[role="menu"] div, span'
                ));
                for (const el of items) {
                    const text = (el.innerText || el.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ');
                    const aria = (el.getAttribute('aria-label') || '');
                    if (/connections/i.test(text + ' ' + aria)) continue;
                    if (!/^connect$/i.test(text) && !( /invite/i.test(aria) && /connect/i.test(aria) )) continue;
                    const target = el.closest('button, a, [role="menuitem"], div.artdeco-dropdown__item') || el;
                    target.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                    target.click();
                    return true;
                }
                return false;
            }"""
        )
    )