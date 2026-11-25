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
cli.py         Typer app. Subcommands + interactive loop (menu ↔ dashboard). Thin wrappers over commands.py.
  └─ commands.py   All business logic: load/save, resolve_name, connect, add/edit/delete, import,
       │            trash/restore, doctor, dashboard_loop (driver), ui_mode resolution.
       ├─ store.py       SSHInstance dataclass, JSON (de)serialization, derive_group_and_tags()
       ├─ health.py      async TCP reachability; check_streaming() for live per-result updates
       ├─ history.py     access history v2 ({"last", "count"}) + frecency scoring
       ├─ settings.py    persisted preferences (~/.config/ssh-conn/settings.json)
       ├─ ssh_import.py  ~/.ssh/config parser
       ├─ theme.py       terminal background detection (dark/light) + colour palettes
       ├─ selector.py    prompt_toolkit modal pickers (fuzzy list, menu) + pure match helpers
       ├─ dashboard.py   full-screen single-surface UI (see invariant below)
       └─ ui.py          ALL rich rendering + prompt_toolkit input. No other module prints.
```

Two interactive UIs share `commands.py`: the classic menu (default) and the
full-screen dashboard. Resolution order for which one starts: `--ui` >
`$SSH_CONN_UI` > `settings.json` (`ssh-conn ui <mode>`) > `"menu"`.

`main.py` and `ssh_conn/__main__.py` are both thin shims calling `ssh_conn.cli.run()`.

## Critical invariants — read before editing

- **`group` and `tags` are derived, never persisted.** `store.derive_group_and_tags(name)` computes them from the instance *name* every time it's loaded. The JSON on disk holds only `hostname`, `username`, `port`, `key_path` (see `SSHInstance.to_dict()`). Any code that constructs an `SSHInstance` must call `derive_group_and_tags(name)` for the `group`/`tags` args, or those fields silently default to `other`/`()`. Renaming an instance re-derives its group/tags. Renames go through `commands._replace_instance` (shared by `edit_interactive` and `rename_instance`): it keeps the entry's position in the JSON and moves the access history (`history.rename_entry`).

- **Group detection matches a known prefix only at the *start* of the name** (`_GROUP_PATTERN` anchored with `^`). Known groups: `OVH, GCP, CL, Buyprotect, Odoo, OVS`. `"Schalcon GCP"` → `other`, not `GCP`. To add a group you must update **both** `store.KNOWN_GROUPS` and the `ui.GROUP_COLORS` / `ui._GROUP_ORDER` tables.

- **`SSHInstance` is a frozen dataclass** — edits create a new instance (`instances[name] = SSHInstance(...)`). The surrounding `instances: dict` *is* mutated in place in `commands.py` (add/edit/delete then `_save`); that dict is the working set, persisted immediately on every change.

- **SSH connection shells out to the system `ssh` binary via `subprocess`** (`commands.connect_by_name`). There is intentionally no `paramiko`. The health check is a raw **TCP** connect (port open?), *not* an SSH handshake — a green dot means the port answers, nothing more.

- **The dashboard never runs business logic (exit-and-reenter).** `dashboard.run()` exits its prompt_toolkit Application returning an `(action, payload)` tuple; `commands.dashboard_loop` executes the action in normal terminal mode and re-enters. Don't call `connect_by_name`/`_save` from inside `dashboard.py`. Live health accumulates in a dict shared across re-entries (background task via `app.create_background_task`); `dashboard.py` uses ANSI colours (not `theme.py` palettes) so it adapts to the terminal theme by itself.

- **History is v2 with lazy normalization** (`history.py`): entries are `{"last": ISO, "count": n}`; legacy plain-string timestamps are normalized on load, never migrated on disk. Frecency (`frecency_scores`) = count × age-bucket weight — the dashboard's idle ordering depends on it.

- **Delete is soft**: `delete_interactive` stashes the removed instance in `trash.json` (`SSH_CONN_TRASH`); `ssh-conn restore` (→ `commands.restore_last`) undoes the last delete only.

## Config & storage resolution

`commands.config_path()` resolves the instances file in this priority order (first hit wins):

1. `--config PATH` / `-c` (sets a module-level `_CONFIG_OVERRIDE` via `set_config_path`)
2. `$SSH_CONN_CONFIG`
3. `~/.config/ssh-conn/config.json` (default) — **cwd-independent**; there is no longer a `./ssh_config.json` cwd fallback.

`commands.migrate_legacy_config()` (called once from the Typer callback, and by `make install`) copies a legacy `./ssh_config.json` from the cwd into the canonical location the first time the app runs — but only when no override/env is set and the canonical file doesn't exist yet. It is non-destructive (copy, not move). This replaces the old silent cwd fallback so the working directory can no longer shadow the real config.

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
