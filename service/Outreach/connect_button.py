import re
from playwright.async_api import Page
from agents.outreach.pipeline_log import log_task
from service.Outreach.match_profilelabel import LabelMatchesProfile
from service.Outreach.profile_display import ProfilePersonName

async def ResolveHeaderConnectButton(page: Page):
    profile_name = await ProfilePersonName(page)
    info = await page.evaluate(
        """(profileName) => {
            const tokens = (profileName || '').split(/\\s+/).filter(t => t.length > 1);
            const escapeRe = (t) => t.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
            const visible = (el) => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden'
                    && rect.width > 2 && rect.height > 2;
            };
            const pack = (el) => {
                const rect = el.getBoundingClientRect();
                return {
                    aria: el.getAttribute('aria-label') || '',
                    text: (el.innerText || '').trim().replace(/\\s+/g, ' '),
                    x: rect.x + rect.width / 2,
                    y: rect.y + rect.height / 2,
                    w: rect.width,
                    h: rect.height,
                    top: rect.top,
                    left: rect.left,
                };
            };
            const nodes = Array.from(document.querySelectorAll('button, a, [role="button"], .artdeco-button'));
            const candidates = [];
            for (const el of nodes) {
                if (!visible(el)) continue;
                const aria = (el.getAttribute('aria-label') || '').trim();
                const text = (el.innerText || '').trim().replace(/\\s+/g, ' ');
                const blob = `${aria} ${text}`;
                if (/connections/i.test(blob)) continue;
                const isInvite = /invite/i.test(aria) && /connect/i.test(aria);
                const isPlain = /^\\+?\\s*connect\\s*$/i.test(text);
                if (!isInvite && !isPlain) continue;
                const p = pack(el);
                // Header band only; exclude deep feed / far-right rail
                if (p.top < 60 || p.top > 520) continue;
                if (p.left > (window.innerWidth * 0.78)) continue;
                let score = 0;
                if (isInvite && tokens.length && tokens.every(t => new RegExp(escapeRe(t), 'i').test(aria))) {
                    score += 100;
                }
                if (el.className && /primary/i.test(String(el.className))) score += 20;
                if (isInvite) score += 10;
                // Prefer higher / more left in the profile action row
                score += Math.max(0, 40 - Math.floor(p.top / 20));
                candidates.push({ el, p, score, aria });
            }
            candidates.sort((a, b) => b.score - a.score || a.p.top - b.p.top || a.p.left - b.p.left);
            if (!candidates.length) return null;
            // If we have a profile name, refuse candidates that invite someone else
            if (tokens.length) {
                const named = candidates.find(c =>
                    /invite/i.test(c.aria) && tokens.every(t => new RegExp(escapeRe(t), 'i').test(c.aria))
                );
                if (named) return named.p;
                const plain = candidates.find(c => /^\\+?\\s*connect\\s*$/i.test(c.p.text));
                if (plain) return plain.p;
                return null;
            }
            return candidates[0].p;
        }""",
        profile_name,
    )
    if not info:
        return None, None
    label = (info.get("aria") or info.get("text") or "Connect").strip()[:120]
    if profile_name and not LabelMatchesProfile(label, profile_name):
        # Plain "Connect" text is OK when name-scoped invite wasn't present
        if not re.search(r"^\s*\+?\s*connect\s*$", label, re.I):
            log_task("Reject Connect candidate (name mismatch)", label=label, profile=profile_name)
            return None, None
    return info, label