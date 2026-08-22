import re
from playwright.async_api import Page
from service.Outreach.profile_card import ProfileRoot
from service.Outreach.profile_display import ProfilePersonName
from agents.outreach.pipeline_log import log_task
from service.Outreach.match_profilelabel import LabelMatchesProfile


async def FindProfileConnectLocator(page: Page):
    """Locate Connect for this profile only (aria must include profile name)."""
    profile_name = await ProfilePersonName(page)
    card = await ProfileRoot(page)

    if profile_name:
        patterns = [
            re.compile(rf"^\s*invite\s+{re.escape(profile_name)}\s+to\s+connect\s*$", re.I),
            re.compile(rf"invite\s+{re.escape(profile_name)}\s+to\s+connect", re.I),
        ]
        for role in ("button", "link"):
            for pat in patterns:
                try:
                    named = page.get_by_role(role, name=pat).first
                    # count() is sync-ish; wait briefly for hydration
                    try:
                        await named.wait_for(state="visible", timeout=2500)
                    except Exception:
                        if await named.count() == 0:
                            continue
                    if await named.count() > 0:
                        label = (await named.get_attribute("aria-label")) or f"Invite {profile_name} to connect"
                        return named, label.strip()[:120]
                except Exception:
                    continue
        # Direct aria-label CSS (works even when role mapping is odd)
        for sel in (
            f'button[aria-label="Invite {profile_name} to connect"]',
            f'a[aria-label="Invite {profile_name} to connect"]',
            f'[aria-label="Invite {profile_name} to connect"]',
            f'button[aria-label*="Invite {profile_name}"][aria-label*="connect" i]',
            f'[aria-label*="Invite {profile_name}"][aria-label*="connect" i]',
        ):
            try:
                loc = page.locator(sel).first
                try:
                    await loc.wait_for(state="visible", timeout=1500)
                except Exception:
                    if await loc.count() == 0:
                        continue
                if await loc.count() > 0 and await loc.is_visible():
                    label = (await loc.get_attribute("aria-label")) or f"Invite {profile_name} to connect"
                    return loc, label.strip()[:120]
            except Exception:
                continue

    candidates = [
        card.locator('button[aria-label*="Invite"][aria-label*="connect" i]'),
        card.locator('a[aria-label*="Invite"][aria-label*="connect" i]'),
        card.locator('[aria-label*="Invite"][aria-label*="connect" i]'),
        card.locator("button.artdeco-button--primary").filter(
            has_text=re.compile(r"^\s*Connect\s*$", re.I)
        ),
        card.locator("button:text-is('Connect')"),
        page.locator("main button.artdeco-button--primary").filter(
            has_text=re.compile(r"^\s*Connect\s*$", re.I)
        ),
    ]
    for loc in candidates:
        try:
            target = loc.first
            if await target.count() == 0:
                continue
            if not await target.is_visible():
                continue
            label = ""
            try:
                label = (await target.get_attribute("aria-label")) or (await target.inner_text()) or ""
            except Exception:
                pass
            if not LabelMatchesProfile(label or "Connect", profile_name):
                log_task("Skip Connect candidate (wrong person)", label=(label or "")[:80], profile=profile_name)
                continue
            box = await target.bounding_box()
            if box and (box["y"] > 560 or box["x"] > 1400):
                continue
            return target, (label or "Connect").strip()[:120]
        except Exception:
            continue
    return None, None