import json
import logging
import re
from typing import Any
import httpx
from config.credential_config import config

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o"
FALLBACK_MODELS = ("gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo")

_INVALID_MODELS = frozenset(
    {
        "gpt-5.5",
        "gpt-5",
        "gpt-5-chat",
        "gpt-5.5-chat",
        "chatgpt-4o-latest",
    }
)


def _clean_model_name(value: str | None) -> str:
    text = (value or "").strip().strip('"').strip("'")
    return text


def resolve_openai_model(model: str | None = None) -> str:
    value = _clean_model_name(model or config.OPENAI_MODEL_NAME or DEFAULT_MODEL)
    if not value:
        return DEFAULT_MODEL
    lowered = value.lower()
    if lowered in _INVALID_MODELS or lowered.startswith("gpt-5"):
        logger.warning("Unsupported OPENAI model '%s'; falling back to %s", value, DEFAULT_MODEL)
        return DEFAULT_MODEL
    return value


def _supports_json_mode(model: str) -> bool:
    lowered = model.lower()
    return not (lowered.startswith("o1") or lowered.startswith("o3"))


def _supports_temperature(model: str) -> bool:
    lowered = model.lower()
    return not (lowered.startswith("o1") or lowered.startswith("o3"))


def _parse_error_body(response: httpx.Response) -> str:
    try:
        payload = response.json()
        err = payload.get("error") or {}
        message = err.get("message") or response.text
        code = err.get("code") or err.get("type") or ""
        return f"{code}: {message}".strip(": ")
    except Exception:
        return response.text[:500]


def _build_payload(
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float | None,
    json_mode: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if temperature is not None and _supports_temperature(model):
        payload["temperature"] = temperature
    if json_mode and _supports_json_mode(model):
        payload["response_format"] = {"type": "json_object"}
    return payload


def _extract_json_content(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            return json.loads(match.group(0))
        raise


async def chat_completion_json(
    *,
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.2,
    timeout: float = 90,
) -> dict[str, Any]:
    """Call OpenAI chat/completions and parse a JSON object response."""
    api_key = (config.OPENAI_API_KEY or "").strip().strip('"').strip("'")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured")

    primary_model = resolve_openai_model(model)
    models_to_try = [primary_model] + [m for m in FALLBACK_MODELS if m != primary_model]

    attempts: list[tuple[str, bool, float | None]] = []
    for attempt_model in models_to_try:
        attempts.append((attempt_model, True, temperature))
        attempts.append((attempt_model, False, temperature))

    last_error = ""
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt_model, json_mode, temp in attempts:
            payload = _build_payload(
                model=attempt_model,
                messages=messages,
                temperature=temp,
                json_mode=json_mode,
            )
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
                return _extract_json_content(content)

            last_error = _parse_error_body(response)
            logger.warning(
                "OpenAI request failed model=%s json_mode=%s status=%s error=%s",
                attempt_model,
                json_mode,
                response.status_code,
                last_error,
            )

            if response.status_code in {401, 403}:
                break

    raise RuntimeError(f"OpenAI chat/completions failed: {last_error}")
