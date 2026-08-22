from __future__ import annotations

from pathlib import Path


DEBUG_DIR = Path(".cache/outreach_debug")


CONNECT_BUTTON_SELECTORS = [
    'button[aria-label*="Invite"][aria-label*="to connect" i]',
    'button[aria-label*="Invite"][aria-label*="connect" i]',
    'main button.artdeco-button--primary:text-is("Connect")',
    'main button:text-is("Connect")',
    'main button.artdeco-button--primary >> text=/^\s*Connect\s*$/',
    'button:text-is("Connect")',
]


MORE_BUTTON_SELECTORS = [
    'main button[aria-label*="More actions" i]',
    'main button[id*="overflow" i]',
    'main button:text-is("More")',
    'button[aria-label*="More actions" i]',
    'button:text-is("More")',
]


PENDING_SELECTORS = [
    'main button:text-is("Pending")',
    'main button:has-text("Pending")',
    'main a:text-is("Pending")',
    'main a:has-text("Pending")',
    'button:text-is("Pending")',
    'button:has-text("Pending")',
    'button[aria-label*="Pending" i]',
    'button:text-is("Withdraw")',
]


MESSAGE_BUTTON_SELECTORS = [
    'main button:text-is("Message")',
    'main a:text-is("Message")',
    'main a:has-text("Message")',
    'button:text-is("Message")',
    'a:text-is("Message")',
    'button[aria-label*="Message" i]:not([aria-label*="Messaging" i])',
]


FOLLOW_SELECTORS = [
    'main button:text-is("Follow")',
    'main button:has-text("Follow")',
    'button:text-is("Follow")',
    'button:has-text("Follow")',
    'button:text-is("Following")',
    'button:has-text("Following")',
]


INVITE_DIALOG = 'div[role="dialog"], div.artdeco-modal, div.send-invite'