# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`ssh-conn` is a single-user CLI (Python ≥3.10) for managing SSH connections to many cloud instances: grouped/colored tables, fuzzy search, parallel TCP health checks, and import from `~/.ssh/config`. It is installed globally via `pipx` and exposes the `ssh-conn` binary. UI text and most prompts are in **Italian** — match that when touching user-facing strings.

## Commands

```bash
make init            # create .venv + install requirements (dev)
make dev-install     # pip install -e .  → binary at .venv/bin/ssh-conn
make start           # python main.py (interactive mode, needs make init first)
make install         # pipx install --force .  (global install)
make uninstall       # pipx uninstall ssh-conn
make clean           # remove .venv, build/, dist/, *.egg-info

python -m ssh_conn   # run the package without installing
```

There is **no test suite, linter, or formatter configured** in this repo (no `pytest`, `ruff`, `black`, or CI). Do not invent test commands. If you add tests, `pytest` is the expected framework per the project rules — wire it up in `pyproject.toml` first.

## Architecture

Strict layering; dependencies flow downward. `commands.py` is the single business-logic layer shared by **both** the CLI-args path and the interactive menu — never duplicate logic into `cli.py`.

```
cli.py         Typer app. Subcommands + interactive loop dispatch. Thin wrappers over commands.py.
  └─ commands.py   All business logic: load/save, resolve_name, connect, add/edit/delete, import.
       ├─ store.py       SSHInstance dataclass, JSON (de)serialization, derive_group_and_tags()
       ├─ health.py      async TCP reachability (asyncio.open_connection)
       ├─ history.py     last-access timestamps
       ├─ ssh_import.py  ~/.ssh/config parser
       └─ ui.py          ALL rich rendering + prompt_toolkit input. No other module prints.
```

`main.py` and `ssh_conn/__main__.py` are both thin shims calling `ssh_conn.cli.run()`.

## Critical invariants — read before editing

- **`group` and `tags` are derived, never persisted.** `store.derive_group_and_tags(name)` computes them from the instance *name* every time it's loaded. The JSON on disk holds only `hostname`, `username`, `port`, `key_path` (see `SSHInstance.to_dict()`). Any code that constructs an `SSHInstance` must call `derive_group_and_tags(name)` for the `group`/`tags` args, or those fields silently default to `other`/`()`. Renaming an instance re-derives its group/tags.

- **Group detection matches a known prefix only at the *start* of the name** (`_GROUP_PATTERN` anchored with `^`). Known groups: `OVH, GCP, CL, Buyprotect, Odoo, OVS`. `"Schalcon GCP"` → `other`, not `GCP`. To add a group you must update **both** `store.KNOWN_GROUPS` and the `ui.GROUP_COLORS` / `ui._GROUP_ORDER` tables.

- **`SSHInstance` is a frozen dataclass** — edits create a new instance (`instances[name] = SSHInstance(...)`). The surrounding `instances: dict` *is* mutated in place in `commands.py` (add/edit/delete then `_save`); that dict is the working set, persisted immediately on every change.

- **SSH connection shells out to the system `ssh` binary via `subprocess`** (`commands.connect_by_name`). There is intentionally no `paramiko`. The health check is a raw **TCP** connect (port open?), *not* an SSH handshake — a green dot means the port answers, nothing more.

## Config & storage resolution

`commands.config_path()` resolves the instances file in this priority order (first hit wins):

1. `--config PATH` / `-c` (sets a module-level `_CONFIG_OVERRIDE` via `set_config_path`)
2. `$SSH_CONN_CONFIG`
3. `./ssh_config.json` — **legacy cwd fallback**: running from the project directory picks up the local file (gitignored). Be aware of this when debugging "wrong config loaded".
4. `~/.config/ssh-conn/config.json` (default)

History is separate: `~/.config/ssh-conn/history.json`, override with `$SSH_CONN_HISTORY`. Health results are never persisted.

## Health check semantics

`health.Status = bool | None`, produced per instance and rendered as a dot in `ui.HEALTH_GLYPHS`:
- `True` → green: TCP port open
- `False` → red: refused / network error
- `None` → yellow: timeout (default `DEFAULT_TIMEOUT = 1.5s`)

All checks run concurrently via `asyncio.gather`; `check_reachability()` wraps it in `asyncio.run` for sync callers.

## Conventions

- **Name resolution logic is duplicated** in `commands.resolve_name` and `ui.select_instance_fuzzy` (exact → case-insensitive → unique-substring → ambiguous). Keep the two behaviors in sync if you change one.
- Prompt helpers in `ui.py` return `None` on cancel (Ctrl-C / EOF / empty). Callers check for `None` and abort — preserve that contract; don't raise from prompts.
- Type annotations everywhere; `from __future__ import annotations` at the top of every module.
- `.ssh/config` import ignores wildcard/negated `Host` patterns (`*`, `?`, `!`) — see `ssh_import.parse_ssh_config`.
