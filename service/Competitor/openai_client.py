import json
import logging
from typing import Any

import httpx

from config.credential_config import config

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o-mini"
FALLBACK_MODEL = "gpt-4o-mini"

# Models that do not exist on /v1/chat/completions or are invalid in many accounts.
_INVALID_MODELS = frozenset(
    {
        "gpt-5.5",
        "gpt-5",
        "gpt-5-chat",
        "gpt-5.5-chat",
        "chatgpt-4o-latest",
    }
)


def resolve_openai_model(model: str | None = None) -> str:
    value = (model or config.OPENAI_MODEL_NAME or DEFAULT_MODEL).strip()
    if not value:
        return DEFAULT_MODEL
    lowered = value.lower()
    if lowered in _INVALID_MODELS or lowered.startswith("gpt-5"):
        logger.warning("Unsupported OPENAI model '%s'; falling back to %s", value, FALLBACK_MODEL)
        return FALLBACK_MODEL
    return value


def _supports_json_mode(model: str) -> bool:
    lowered = model.lower()
    if lowered.startswith("o1") or lowered.startswith("o3"):
        return False
    return True


def _supports_temperature(model: str) -> bool:
    lowered = model.lower()
    return not (lowered.startswith("o1") or lowered.startswith("o3"))


def _build_payload(
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    json_mode: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if _supports_temperature(model):
        payload["temperature"] = temperature
    if json_mode and _supports_json_mode(model):
        payload["response_format"] = {"type": "json_object"}
    return payload


async def chat_completion_json(
    *,
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.2,
    timeout: float = 90,
) -> dict[str, Any]:
    """
    Call OpenAI chat/completions and parse a JSON object response.
    Retries with safe defaults when the configured model rejects the request.
    """
    api_key = (config.OPENAI_API_KEY or "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured")

    primary_model = resolve_openai_model(model)
    attempts: list[tuple[str, bool, float | None]] = [
        (primary_model, True, temperature if _supports_temperature(primary_model) else None),
        (FALLBACK_MODEL, True, temperature),
        (FALLBACK_MODEL, False, temperature),
    ]

    last_error = ""
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt_model, json_mode, temp in attempts:
            payload = _build_payload(
                model=attempt_model,
                messages=messages,
                temperature=temp if temp is not None else 0.2,
                json_mode=json_mode,
            )
            if temp is None:
                payload.pop("temperature", None)

            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"] or "{}"
                return json.loads(content)

            last_error = response.text[:500]
            logger.warning(
                "OpenAI chat/completions failed model=%s json_mode=%s status=%s body=%s",
                attempt_model,
                json_mode,
                response.status_code,
                last_error,
            )

    raise RuntimeError(f"OpenAI chat/completions failed: {last_error}")
