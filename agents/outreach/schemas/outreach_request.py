from __future__ import annotations
import re
from typing import Any
from pydantic import BaseModel, Field, field_validator

LINKEDIN_IN_RE = re.compile(
    r"(?:https?://)?(?:[\w.-]+\.)?linkedin\.com/in/([A-Za-z0-9_-]+)/?",
    re.I,
)


def normalize_linkedin_username(value: str) -> str:
    text = (value or "").strip().lstrip("@")
    if not text:
        raise ValueError("linkedin_username is required")
    match = LINKEDIN_IN_RE.search(text if "linkedin.com" in text else "")
    if match:
        return match.group(1)
    if "/" in text or " " in text:
        raise ValueError(
            "Provide a LinkedIn username (e.g. john-doe) or profile URL "
            "(https://www.linkedin.com/in/john-doe/)"
        )
    return text


class LinkedInOutreachRequest(BaseModel):
    linkedin_username: str = Field(
        ...,
        description="LinkedIn /in/ username or full profile URL",
        examples=["john-doe", "https://www.linkedin.com/in/john-doe/"],
    )
    connection_note: str | None = Field(
        default=None,
        max_length=300,
        description="Optional note sent with the connection request (LinkedIn limit ~300 chars)",
    )
    message: str | None = Field(
        default=None,
        max_length=8000,
        description="Message to send if already connected, or after connect when possible",
    )
    send_connection: bool = Field(
        default=True,
        description="Send a connection request when not already connected",
    )
    send_message: bool = Field(
        default=True,
        description="Send a direct message when already connected (or after connect if messaging is available)",
    )
    headless: bool = Field(
        default=True,
        description="Run Playwright headless. Set false to watch the browser.",
    )

    @field_validator("linkedin_username")
    @classmethod
    def _validate_username(cls, value: str) -> str:
        return normalize_linkedin_username(value)

    def profile_url(self) -> str:
        return f"https://www.linkedin.com/in/{self.linkedin_username}/"

    def to_agent_config(self) -> dict[str, Any]:
        return {
            "linkedin_username": self.linkedin_username,
            "profile_url": self.profile_url(),
            "connection_note": (self.connection_note or "").strip(),
            "message": (self.message or "").strip(),
            "send_connection": self.send_connection,
            "send_message": self.send_message,
            "headless": self.headless,
        }
