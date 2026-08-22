from playwright.async_api import Page

async def ReadLinkedinToast(page: Page) -> str:
    """Read visible LinkedIn toast / snackbar text (cooldown, invite errors, etc.)."""
    try:
        return str(
            await page.evaluate(
                r"""() => {
                    const sels = [
                        'div[data-test-artdeco-toast-item]',
                        '.artdeco-toast-item',
                        '.artdeco-toast-item__message',
                        'div[role="alert"]',
                    ];
                    for (const sel of sels) {
                        for (const el of document.querySelectorAll(sel)) {
                            const style = window.getComputedStyle(el);
                            const r = el.getBoundingClientRect();
                            if (style.display === 'none' || style.visibility === 'hidden') continue;
                            if (r.width < 20 || r.height < 10) continue;
                            const t = (el.innerText || '').trim().replace(/\s+/g, ' ');
                            if (t) return t.slice(0, 240);
                        }
                    }
                    return '';
                }"""
            )
            or ""
        )
    except Exception:
        return ""



def ToastIsResendCoolDown(toast: str) -> bool:
    t = (toast or "").lower()
    return ("resend" in t and "week" in t) or ("after withdrawing" in t) or (
        "invitation not sent" in t and "withdraw" in t
    )
