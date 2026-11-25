"""Track per-instance access history in ~/.config/ssh-conn/history.json.

Storage format (v2): {"<name>": {"last": "<ISO-8601>", "count": <int>}}.
Legacy v1 entries ("<name>": "<ISO-8601>") are normalised on load, so no
migration of existing files is required.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DEFAULT_HISTORY_PATH = Path.home() / ".config" / "ssh-conn" / "history.json"

# Frecency: weight per age bucket (max age seconds → weight).
# score = access count * weight of the most recent access.
_FRECENCY_BUCKETS: tuple[tuple[int, float], ...] = (
    (3600, 4.0),
    (86400, 2.0),
    (7 * 86400, 1.0),
    (30 * 86400, 0.5),
)
_FRECENCY_OLDEST_WEIGHT = 0.25


def _history_path() -> Path:
    env = os.environ.get("SSH_CONN_HISTORY")
    return Path(env) if env else DEFAULT_HISTORY_PATH


def _normalize_entry(value: object) -> dict | None:
    if isinstance(value, str):
        return {"last": value, "count": 1}
    if isinstance(value, dict) and "last" in value:
        try:
            count = max(1, int(value.get("count", 1)))
        except (TypeError, ValueError):
            count = 1
        return {"last": str(value["last"]), "count": count}
    return None


def load_history() -> dict[str, dict]:
    path = _history_path()
    if not path.exists():
        return {}
    try:
        with path.open("r") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    normalized: dict[str, dict] = {}
    for key, value in data.items():
        entry = _normalize_entry(value) if isinstance(key, str) else None
        if entry is not None:
            normalized[key] = entry
    return normalized


def record_access(name: str) -> None:
    path = _history_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    history = load_history()
    previous = history.get(name)
    count = previous["count"] + 1 if previous else 1
    updated = {
        **history,
        name: {
            "last": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "count": count,
        },
    }
    try:
        with path.open("w") as f:
            json.dump(updated, f, indent=2)
    except OSError:
        pass


def rename_entry(old: str, new: str) -> None:
    """Move the history of `old` under `new`, so a rename keeps recency/frecency.

    A stale entry already stored under `new` (e.g. a deleted instance with the
    same name) is replaced. No-op when `old` has no history.
    """
    history = load_history()
    if old == new or old not in history:
        return
    updated = {k: v for k, v in history.items() if k not in (old, new)}
    updated[new] = history[old]
    try:
        with _history_path().open("w") as f:
            json.dump(updated, f, indent=2)
    except OSError:
        pass  # history is best-effort, like record_access


def recent_names(known: set[str] | None = None, limit: int = 5) -> list[str]:
    history = load_history()
    items = sorted(history.items(), key=lambda kv: kv[1]["last"], reverse=True)
    if known is not None:
        items = [(n, e) for n, e in items if n in known]
    return [n for n, _ in items[:limit]]


def last_access(name: str) -> str | None:
    entry = load_history().get(name)
    return entry["last"] if entry else None


def _parse_ts(iso_timestamp: str) -> datetime | None:
    try:
        ts = datetime.fromisoformat(iso_timestamp)
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def frecency_scores() -> dict[str, float]:
    """Score per instance: access count weighted by recency of the last access."""
    now = datetime.now(timezone.utc)
    scores: dict[str, float] = {}
    for name, entry in load_history().items():
        ts = _parse_ts(entry["last"])
        if ts is None:
            continue
        age = max(0.0, (now - ts).total_seconds())
        weight = next(
            (w for limit, w in _FRECENCY_BUCKETS if age < limit),
            _FRECENCY_OLDEST_WEIGHT,
        )
        scores[name] = entry["count"] * weight
    return scores


def frecency_order(names: Iterable[str]) -> list[str]:
    """`names` sorted by frecency (highest first), then alphabetically."""
    scores = frecency_scores()
    return sorted(names, key=lambda n: (-scores.get(n, 0.0), n.lower()))


def time_ago(iso_timestamp: str) -> str:
    ts = _parse_ts(iso_timestamp)
    if ts is None:
        return ""
    delta = datetime.now(timezone.utc) - ts
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "in futuro"
    if seconds < 60:
        return "ora"
    if seconds < 3600:
        return f"{seconds // 60}min fa"
    if seconds < 86400:
        return f"{seconds // 3600}h fa"
    if seconds < 86400 * 30:
        return f"{seconds // 86400}g fa"
    return f"{seconds // (86400 * 30)} mesi fa"
