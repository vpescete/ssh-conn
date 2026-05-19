"""Track per-instance last-access timestamps in ~/.config/ssh-conn/history.json."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_HISTORY_PATH = Path.home() / ".config" / "ssh-conn" / "history.json"


def _history_path() -> Path:
    env = os.environ.get("SSH_CONN_HISTORY")
    return Path(env) if env else DEFAULT_HISTORY_PATH


def load_history() -> dict[str, str]:
    path = _history_path()
    if not path.exists():
        return {}
    try:
        with path.open("r") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return {k: str(v) for k, v in data.items() if isinstance(k, str)}


def record_access(name: str) -> None:
    path = _history_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    history = load_history()
    history[name] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with path.open("w") as f:
            json.dump(history, f, indent=2)
    except OSError:
        pass


def recent_names(known: set[str] | None = None, limit: int = 5) -> list[str]:
    history = load_history()
    items = sorted(history.items(), key=lambda kv: kv[1], reverse=True)
    if known is not None:
        items = [(n, t) for n, t in items if n in known]
    return [n for n, _ in items[:limit]]


def last_access(name: str) -> str | None:
    return load_history().get(name)


def time_ago(iso_timestamp: str) -> str:
    try:
        ts = datetime.fromisoformat(iso_timestamp)
    except ValueError:
        return ""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - ts
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "in futuro"
    if seconds < 60:
        return "ora"
    if seconds < 3600:
        return f"{seconds // 60}m fa"
    if seconds < 86400:
        return f"{seconds // 3600}h fa"
    if seconds < 86400 * 30:
        return f"{seconds // 86400}g fa"
    return f"{seconds // (86400 * 30)}M fa"
