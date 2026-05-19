"""Parse OpenSSH config (~/.ssh/config) and return SSHInstance objects."""
from __future__ import annotations

import os
from pathlib import Path

from .store import SSHInstance, derive_group_and_tags


def parse_ssh_config(path: str | Path = "~/.ssh/config") -> list[SSHInstance]:
    p = Path(os.path.expanduser(str(path)))
    if not p.exists():
        return []

    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    try:
        text = p.read_text()
    except OSError:
        return []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        key = parts[0].lower()
        value = parts[1].strip()
        if key == "host":
            for host_pattern in value.split():
                if any(ch in host_pattern for ch in ("*", "?", "!")):
                    current = None
                    continue
                block = {"_name": host_pattern}
                blocks.append(block)
                current = block
        elif current is not None:
            current[key] = value

    default_user = os.environ.get("USER") or "root"
    instances: list[SSHInstance] = []
    for block in blocks:
        name = block.get("_name", "")
        hostname = block.get("hostname", name)
        username = block.get("user", default_user)
        try:
            port = int(block.get("port", "22"))
        except ValueError:
            port = 22
        key_path = block.get("identityfile")
        if not name or not hostname:
            continue
        group, tags = derive_group_and_tags(name)
        instances.append(
            SSHInstance(
                name=name,
                hostname=hostname,
                username=username,
                port=port,
                key_path=key_path,
                group=group,
                tags=tags,
            )
        )
    return instances
