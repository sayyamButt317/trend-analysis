from __future__ import annotations

from typing import Any

from service.Competitor.openai_client import chat_completion_json


async def complete_json(
    *,
    system: str,
    user: str,
    temperature: float = 0.4,
) -> dict[str, Any]:
    return await chat_completion_json(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        timeout=120,
    )
