"""Optional OpenAI configuration saved in the OS credential store."""

from __future__ import annotations

import json
from typing import Any

_SERVICE_NAME = "replyguard.local"
_USERNAME = "openai-settings"


def _keyring():
    try:
        import keyring
    except ImportError as exc:
        raise RuntimeError(
            "Install the pipeline dependencies to enable local credential storage."
        ) from exc
    return keyring


def get_openai_settings() -> dict[str, str] | None:
    raw = _keyring().get_password(_SERVICE_NAME, _USERNAME)
    if not raw:
        return None
    try:
        value: Any = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Saved OpenAI settings could not be read.") from exc
    if not isinstance(value, dict):
        raise RuntimeError("Saved OpenAI settings have an invalid format.")
    api_key = value.get("api_key")
    model = value.get("model")
    if not isinstance(api_key, str) or not api_key.strip():
        raise RuntimeError("Saved OpenAI settings do not contain an API key.")
    if not isinstance(model, str) or not model.strip():
        raise RuntimeError("Saved OpenAI settings do not contain a model ID.")
    return {"api_key": api_key.strip(), "model": model.strip()}


def save_openai_settings(api_key: str, model: str) -> None:
    clean_key = api_key.strip()
    clean_model = model.strip()
    if not clean_key:
        raise ValueError("Enter an OpenAI API key.")
    if not clean_model:
        raise ValueError("Enter an OpenAI model ID.")
    payload = json.dumps(
        {"api_key": clean_key, "model": clean_model},
        separators=(",", ":"),
    )
    _keyring().set_password(_SERVICE_NAME, _USERNAME, payload)


def clear_openai_settings() -> None:
    keyring = _keyring()
    try:
        keyring.delete_password(_SERVICE_NAME, _USERNAME)
    except keyring.errors.PasswordDeleteError:
        pass
