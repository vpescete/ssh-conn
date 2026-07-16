"""Persisted user preferences in ~/.config/ssh-conn/settings.json.

Currently stores only the preferred interactive UI ("menu" | "dashboard").
Override the file location with $SSH_CONN_SETTINGS (mainly for tests).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_SETTINGS_PATH = Path.home() / ".config" / "ssh-conn" / "settings.json"

VALID_UI_MODES: tuple[str, ...] = ("menu", "dashboard")


def _settings_path() -> Path:
    env = os.environ.get("SSH_CONN_SETTINGS")
    return Path(env).expanduser() if env else DEFAULT_SETTINGS_PATH


def load_settings() -> dict:
    path = _settings_path()
    if not path.exists():
        return {}
    try:
        with path.open("r") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_setting(key: str, value: object) -> bool:
    """Persist a single setting; returns False (without raising) on I/O errors."""
    path = _settings_path()
    updated = {**load_settings(), key: value}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            json.dump(updated, f, indent=2)
    except OSError:
        return False
    return True


def ui_preference() -> str | None:
    """The saved UI mode, or None if unset/invalid."""
    value = load_settings().get("ui")
    return value if value in VALID_UI_MODES else None
