from __future__ import annotations

from typing import Any, Optional, TypedDict


class OutreachResult(TypedDict, total=False):
    username: str
    profile_url: str
    profile_opened: bool
    connection_status: str
    connection_sent: bool
    note_sent: bool
    message_sent: bool
    already_connected: bool
    error: Optional[str]
    details: dict[str, Any]


class OutreachState(TypedDict, total=False):
    """LangGraph state for LinkedIn outreach."""

    config: dict[str, Any]
    linkedin_username: str
    profile_url: str
    connection_note: str
    message: str
    send_connection: bool
    send_message: bool

    profile_opened: bool
    connection_status: str
    connection_sent: bool
    note_sent: bool
    message_sent: bool
    already_connected: bool

    result: OutreachResult
    error: Optional[str]
    logs: list[str]
