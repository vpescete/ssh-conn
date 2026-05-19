"""Storage layer: SSHInstance dataclass, JSON load/save, auto-detect group/tags."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

KNOWN_GROUPS: tuple[str, ...] = ("OVH", "GCP", "CL", "Buyprotect", "Odoo", "OVS")
_GROUP_PATTERN = re.compile(rf"^({'|'.join(KNOWN_GROUPS)})\b", re.IGNORECASE)
_ENV_TOKENS = {
    "prod": "prod",
    "production": "prod",
    "staging": "staging",
    "stage": "staging",
    "dev": "dev",
    "develop": "dev",
    "development": "dev",
    "test": "test",
    "testing": "test",
    "qa": "qa",
    "uat": "uat",
}
_NOISE_TOKENS = {"the", "il", "la", "di", "gruppo", "vm", "instance", "istanza", "server", ""}


@dataclass(frozen=True)
class SSHInstance:
    name: str
    hostname: str
    username: str
    port: int = 22
    key_path: str | None = None
    group: str = "other"
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        """Return only canonical schema fields — group/tags are derived in-memory."""
        return {
            "hostname": self.hostname,
            "username": self.username,
            "port": self.port,
            "key_path": self.key_path,
        }


def derive_group_and_tags(name: str) -> tuple[str, tuple[str, ...]]:
    stripped = name.strip()
    match = _GROUP_PATTERN.match(stripped)
    if match:
        matched = match.group(1)
        canonical_map = {g.upper(): g for g in KNOWN_GROUPS}
        group = canonical_map.get(matched.upper(), matched)
        rest = stripped[match.end():]
    else:
        group = "other"
        rest = stripped

    raw_tokens = re.split(r"[\s\-_/:.,]+", rest.lower())
    tags: list[str] = []
    seen: set[str] = set()
    for token in raw_tokens:
        if not token or token in _NOISE_TOKENS:
            continue
        normalized = _ENV_TOKENS.get(token, token)
        if normalized in seen:
            continue
        seen.add(normalized)
        tags.append(normalized)
    return group, tuple(tags)


def instance_from_dict(name: str, data: dict) -> SSHInstance:
    group, tags = derive_group_and_tags(name)
    return SSHInstance(
        name=name,
        hostname=str(data["hostname"]),
        username=str(data["username"]),
        port=int(data.get("port", 22)),
        key_path=data.get("key_path"),
        group=group,
        tags=tags,
    )


def load_instances(config_path: str | Path) -> dict[str, SSHInstance]:
    path = Path(config_path)
    if not path.exists():
        return {}
    with path.open("r") as f:
        raw = json.load(f)
    return {name: instance_from_dict(name, data) for name, data in raw.items()}


def save_instances(instances: dict[str, SSHInstance], config_path: str | Path) -> None:
    serializable = {name: inst.to_dict() for name, inst in instances.items()}
    path = Path(config_path)
    with path.open("w") as f:
        json.dump(serializable, f, indent=4)
