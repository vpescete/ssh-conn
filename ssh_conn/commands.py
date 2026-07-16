"""Business logic for ssh-conn commands. Used both by CLI args and interactive loop."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from . import (
    dashboard,
    health,
    history,
    selector,
    settings,
    ssh_import,
    store,
    theme,
    ui,
)

DEFAULT_KEY_PATH = "~/.ssh/id_ed25519"
DEFAULT_USER_CONFIG = Path.home() / ".config" / "ssh-conn" / "config.json"
DEFAULT_TRASH_PATH = Path.home() / ".config" / "ssh-conn" / "trash.json"
LEGACY_CWD_CONFIG = Path("ssh_config.json")

VALID_UI: tuple[str, ...] = settings.VALID_UI_MODES

_CONFIG_OVERRIDE: Path | None = None
_UI_OVERRIDE: str | None = None


def set_config_path(path: str | Path | None) -> None:
    global _CONFIG_OVERRIDE
    _CONFIG_OVERRIDE = Path(str(path)).expanduser() if path else None


def config_path() -> Path:
    if _CONFIG_OVERRIDE is not None:
        return _CONFIG_OVERRIDE
    env = os.environ.get("SSH_CONN_CONFIG")
    if env:
        return Path(env).expanduser()
    return DEFAULT_USER_CONFIG


def migrate_legacy_config() -> Path | None:
    """Copy a legacy ./ssh_config.json into the canonical location, once.

    Runs only when no --config/env is set, the canonical file does not yet
    exist, and a legacy file exists in the current directory. Non-destructive
    (copy, not move) so nothing is lost. Returns the target path if it copied.
    """
    if _CONFIG_OVERRIDE is not None or os.environ.get("SSH_CONN_CONFIG"):
        return None
    legacy = LEGACY_CWD_CONFIG
    target = DEFAULT_USER_CONFIG
    if target.exists() or not legacy.exists():
        return None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy, target)
    except OSError as exc:
        ui.print_warning(f"Migrazione config non riuscita ({exc}).")
        return None
    ui.print_success(f"Config migrata in {target}")
    ui.print_info(
        f"Trovato {legacy.resolve()} nella cartella corrente e copiato nella "
        "sede canonica (usata da qualsiasi directory). L'originale è rimasto al suo posto."
    )
    return target


def set_ui_mode(value: str | None) -> None:
    """Explicit --ui override; None re-enables env/settings resolution."""
    global _UI_OVERRIDE
    _UI_OVERRIDE = value if value in VALID_UI else None


def has_ui_override() -> bool:
    return _UI_OVERRIDE is not None


def ui_mode() -> str:
    """Active interactive UI: --ui > $SSH_CONN_UI > settings.json > menu."""
    if _UI_OVERRIDE is not None:
        return _UI_OVERRIDE
    env = os.environ.get("SSH_CONN_UI", "").strip().lower()
    if env in VALID_UI:
        return env
    return settings.ui_preference() or "menu"


def load() -> dict[str, store.SSHInstance]:
    return store.load_instances(config_path())


def _save(instances: dict[str, store.SSHInstance]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    store.save_instances(instances, path)


def _parse_port(value: str) -> int | None:
    try:
        port = int(value)
    except ValueError:
        ui.print_error(f"Porta non valida: '{value}'.")
        return None
    if not 1 <= port <= 65535:
        ui.print_error(f"Porta fuori range (1-65535): {port}.")
        return None
    return port


def resolve_name(
    instances: dict[str, store.SSHInstance], query: str
) -> str | None:
    if query in instances:
        return query
    lower_map = {n.lower(): n for n in instances}
    if query.lower() in lower_map:
        return lower_map[query.lower()]
    matches = [n for n in instances if query.lower() in n.lower()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        ui.print_error(f"Nessuna istanza trovata per '{query}'.")
        return None
    ui.print_error(
        f"Match ambiguo per '{query}': {', '.join(matches[:5])}"
    )
    return None


def last_used_name(instances: dict[str, store.SSHInstance]) -> str | None:
    recent = history.recent_names(known=set(instances.keys()), limit=1)
    return recent[0] if recent else None


def connect_last(instances: dict[str, store.SSHInstance]) -> int:
    name = last_used_name(instances)
    if not name:
        ui.print_warning("Nessuna connessione recente da riprendere.")
        return 1
    return connect_by_name(instances, name)


def connect_by_name(
    instances: dict[str, store.SSHInstance], name: str
) -> int:
    inst = instances[name]
    cmd: list[str] = ["ssh"]
    if inst.port != 22:
        cmd += ["-p", str(inst.port)]
    if inst.key_path:
        cmd += ["-i", os.path.expanduser(inst.key_path)]
    cmd.append(f"{inst.username}@{inst.hostname}")
    ui.print_connecting(name, " ".join(cmd))
    history.record_access(name)
    try:
        result = subprocess.run(cmd)
    except FileNotFoundError:
        ui.print_error("Comando 'ssh' non trovato nel PATH.")
        return 127
    if result.returncode != 0:
        ui.print_warning(f"Sessione terminata con codice {result.returncode}.")
    return result.returncode


def list_view(
    instances: dict[str, store.SSHInstance],
    filter_terms: Iterable[str] = (),
    check_health: bool = False,
    show_numbers: bool = False,
) -> dict[str, store.SSHInstance]:
    terms = [t for t in filter_terms if t]
    filtered = ui.filter_instances(instances, terms)
    if instances and terms and not filtered:
        ui.print_warning(f"Nessun risultato per i filtri: {' '.join(terms)}")
        ui.print_info("I filtri sono in AND su nome, host, user, gruppo e tag.")
        return {}
    health_map = None
    if check_health:
        with ui.status(f"🩺 Health check su {len(filtered)} istanze..."):
            health_map = health.check_reachability(filtered)
    ui.render_instance_table(filtered, health=health_map, show_numbers=show_numbers)
    return filtered


def list_interactive(instances: dict[str, store.SSHInstance]) -> None:
    ui.clear_screen()
    raw = ui.prompt_optional("Filtra (es. 'ovh prod', Invio per tutte)")
    if raw is None:
        return
    terms = raw.split() if raw else []
    filtered = list_view(instances, terms, show_numbers=True)
    if not filtered:
        return
    order = ui.ordered_names(filtered)
    choice = ui.prompt_optional("Numero da connettere (Invio per tornare al menu)")
    if choice is None or not choice:
        return
    if not choice.isdigit() or not 1 <= int(choice) <= len(order):
        ui.print_error(f"Numero non valido: '{choice}'.")
        return
    connect_by_name(filtered, order[int(choice) - 1])


def connect_interactive(instances: dict[str, store.SSHInstance]) -> None:
    ui.clear_screen()
    if not instances:
        ui.print_warning("Nessuna istanza configurata.")
        return
    name = ui.select_instance_fuzzy(instances, prompt_label="Connetti a")
    if not name:
        return
    connect_by_name(instances, name)


def add_interactive(instances: dict[str, store.SSHInstance]) -> None:
    ui.clear_screen()
    ui.print_info("=== Aggiungi nuova istanza ===\n")

    name = ui.prompt_text("Nome istanza")
    if not name:
        ui.print_warning("Annullato.")
        return
    if name in instances:
        ui.print_error(f"Istanza '{name}' esiste già.")
        return

    hostname = ui.prompt_text("Hostname")
    if not hostname:
        ui.print_warning("Annullato.")
        return

    username = ui.prompt_text("Username")
    if not username:
        ui.print_warning("Annullato.")
        return

    key_path: str | None = None
    if ui.prompt_confirm("Usare chiave SSH?", default=True):
        kp = ui.prompt_optional(
            f"Percorso chiave (Invio per default {DEFAULT_KEY_PATH})"
        )
        if kp is None:
            ui.print_warning("Annullato.")
            return
        key_path = kp or DEFAULT_KEY_PATH

    port = 22
    if ui.prompt_confirm("Opzioni avanzate (porta custom)?", default=False):
        p_str = ui.prompt_optional("Porta", default="22")
        if p_str is None:
            ui.print_warning("Annullato.")
            return
        if p_str:
            parsed = _parse_port(p_str)
            if parsed is None:
                return
            port = parsed

    group, tags = store.derive_group_and_tags(name)
    inst = store.SSHInstance(
        name=name,
        hostname=hostname,
        username=username,
        port=port,
        key_path=key_path,
        group=group,
        tags=tags,
    )
    ui.print_info(f"\n=== Riepilogo '{name}' (gruppo {group}) ===")
    ui.print_ssh_command(inst)
    if not ui.prompt_confirm("Salvare questa istanza?", default=True):
        ui.print_warning("Annullato, niente salvato.")
        return
    instances[name] = inst
    _save(instances)
    ui.print_success(f"Istanza '{name}' aggiunta.")


def edit_interactive(
    instances: dict[str, store.SSHInstance], name: str | None = None
) -> None:
    ui.clear_screen()
    if not instances:
        ui.print_warning("Nessuna istanza da modificare.")
        return
    if name is None:
        name = ui.select_instance_fuzzy(instances, prompt_label="Modifica")
    if not name:
        return
    if name not in instances:
        ui.print_error(f"Istanza '{name}' non trovata.")
        return
    current = instances[name]
    ui.print_info(
        f"\n=== Modifica '{name}' === (Invio per mantenere il valore attuale)\n"
    )

    new_hostname = ui.prompt_optional("Hostname", default=current.hostname)
    if new_hostname is None:
        ui.print_warning("Annullato.")
        return
    if not new_hostname:
        ui.print_error("Hostname non può essere vuoto.")
        return

    new_username = ui.prompt_optional("Username", default=current.username)
    if new_username is None:
        ui.print_warning("Annullato.")
        return
    if not new_username:
        ui.print_error("Username non può essere vuoto.")
        return

    current_key = current.key_path or ""
    key_input = ui.prompt_optional(
        "Chiave SSH ('-' per rimuovere)", default=current_key
    )
    if key_input is None:
        ui.print_warning("Annullato.")
        return
    if key_input == "-" or key_input == "":
        new_key: str | None = None
    else:
        new_key = key_input

    new_port = current.port
    show_port = current.port != 22 or ui.prompt_confirm(
        "Modificare porta (attuale 22)?", default=False
    )
    if show_port:
        p_str = ui.prompt_optional("Porta", default=str(current.port))
        if p_str is None:
            ui.print_warning("Annullato.")
            return
        if p_str:
            parsed = _parse_port(p_str)
            if parsed is None:
                return
            new_port = parsed

    group, tags = store.derive_group_and_tags(name)
    instances[name] = store.SSHInstance(
        name=name,
        hostname=new_hostname,
        username=new_username,
        port=new_port,
        key_path=new_key,
        group=group,
        tags=tags,
    )
    _save(instances)
    ui.print_success(f"Istanza '{name}' aggiornata.")
    ui.print_ssh_command(instances[name])


def delete_interactive(
    instances: dict[str, store.SSHInstance], name: str | None = None
) -> None:
    ui.clear_screen()
    if not instances:
        ui.print_warning("Nessuna istanza da eliminare.")
        return
    if name is None:
        name = ui.select_instance_fuzzy(instances, prompt_label="Elimina")
    if not name:
        return
    if name not in instances:
        ui.print_error(f"Istanza '{name}' non trovata.")
        return
    if not ui.prompt_confirm(f"Eliminare '{name}'?", default=False):
        ui.print_warning("Annullato.")
        return
    deleted = instances[name]
    del instances[name]
    _save(instances)
    _stash_deleted(deleted)
    ui.print_success(f"Istanza '{name}' eliminata.")
    ui.print_info("Ripristinala con: ssh-conn restore")


def health_view(instances: dict[str, store.SSHInstance]) -> None:
    ui.clear_screen()
    if not instances:
        ui.print_warning("Nessuna istanza da controllare.")
        return
    with ui.status(f"🩺 Health check su {len(instances)} istanze..."):
        results = health.check_reachability(instances)
    ui.render_instance_table(instances, health=results)


def import_ssh_config(
    instances: dict[str, store.SSHInstance],
    source: str = "~/.ssh/config",
    overwrite: bool = False,
) -> tuple[int, int]:
    parsed = ssh_import.parse_ssh_config(source)
    if not parsed:
        ui.print_warning(f"Nessuna istanza trovata in {source}.")
        return 0, 0
    added = 0
    skipped = 0
    for inst in parsed:
        if inst.name in instances and not overwrite:
            skipped += 1
            continue
        instances[inst.name] = inst
        added += 1
    if added:
        _save(instances)
    ui.print_success(
        f"Importate {added} istanze da {source}"
        + (f" (saltate {skipped} già esistenti)" if skipped else "")
    )
    return added, skipped


def import_ssh_config_interactive(
    instances: dict[str, store.SSHInstance],
) -> None:
    ui.clear_screen()
    source = ui.prompt_optional(
        "Percorso ssh config", default=os.path.expanduser("~/.ssh/config")
    )
    if source is None or not source:
        ui.print_warning("Annullato.")
        return
    parsed = ssh_import.parse_ssh_config(source)
    if not parsed:
        ui.print_warning(f"Nessuna istanza importabile da {source}.")
        return
    new_names = [p.name for p in parsed if p.name not in instances]
    dup_names = [p.name for p in parsed if p.name in instances]
    ui.print_info(
        f"Trovate {len(parsed)} istanze: {len(new_names)} nuove, "
        f"{len(dup_names)} già presenti."
    )
    overwrite = False
    if dup_names and ui.prompt_confirm(
        "Sovrascrivere le istanze già esistenti?", default=False
    ):
        overwrite = True
    if not ui.prompt_confirm("Procedere con l'import?", default=True):
        ui.print_warning("Annullato.")
        return
    import_ssh_config(instances, source=source, overwrite=overwrite)


# ------------------------------------------------------------------ trash --


def _trash_path() -> Path:
    env = os.environ.get("SSH_CONN_TRASH")
    return Path(env).expanduser() if env else DEFAULT_TRASH_PATH


def _stash_deleted(inst: store.SSHInstance) -> None:
    """Keep the last deleted instance so `ssh-conn restore` can undo."""
    entry = {
        "name": inst.name,
        "data": inst.to_dict(),
        "deleted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    path = _trash_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            json.dump(entry, f, indent=2)
    except OSError as exc:
        ui.print_warning(f"Cestino non aggiornato ({exc}): ripristino non disponibile.")


def _load_trash() -> dict | None:
    path = _trash_path()
    if not path.exists():
        return None
    try:
        with path.open("r") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or "name" not in data or "data" not in data:
        return None
    return data


def restore_last(instances: dict[str, store.SSHInstance]) -> int:
    """Undo the most recent delete. Returns a process exit code."""
    entry = _load_trash()
    if entry is None:
        ui.print_warning("Nessuna istanza eliminata di recente da ripristinare.")
        return 1
    name = str(entry["name"])
    if name in instances and not ui.prompt_confirm(
        f"'{name}' esiste già. Sovrascrivere?", default=False
    ):
        ui.print_warning("Annullato.")
        return 1
    try:
        instances[name] = store.instance_from_dict(name, entry["data"])
    except (KeyError, TypeError, ValueError) as exc:
        ui.print_error(f"Dati del cestino non validi: {exc}")
        return 1
    _save(instances)
    try:
        _trash_path().unlink()
    except OSError:
        pass  # restored anyway; a stale trash file is harmless
    ui.print_success(f"Istanza '{name}' ripristinata.")
    return 0


# ----------------------------------------------------------------- doctor --


def doctor() -> int:
    """Diagnose environment and configuration. Returns a process exit code."""
    problems = 0

    def check(is_ok: bool, label: str, detail: str, warn_only: bool = False) -> None:
        nonlocal problems
        icon = "✅" if is_ok else ("⚠️ " if warn_only else "❌")
        if not is_ok and not warn_only:
            problems += 1
        ui.console.print(f"  {icon} [bold]{label}[/]: {detail}")

    ssh_path = shutil.which("ssh")
    check(bool(ssh_path), "ssh", ssh_path or "non trovato nel PATH")

    path = config_path()
    if path.exists():
        try:
            instances = store.load_instances(path)
            check(True, "config", f"{path} ({len(instances)} istanze)")
        except (OSError, ValueError) as exc:
            instances = {}
            check(False, "config", f"{path} non leggibile: {exc}")
    else:
        instances = {}
        check(True, "config", f"{path} non esiste (creata al primo salvataggio)")

    missing = [
        i.name
        for i in instances.values()
        if i.key_path and not Path(os.path.expanduser(i.key_path)).exists()
    ]
    loose = [
        i.name
        for i in instances.values()
        if i.key_path
        and Path(os.path.expanduser(i.key_path)).exists()
        and Path(os.path.expanduser(i.key_path)).stat().st_mode & 0o077
    ]
    check(
        not missing,
        "chiavi",
        "tutte presenti" if not missing else f"mancanti per: {', '.join(missing[:5])}",
        warn_only=True,
    )
    check(
        not loose,
        "permessi chiavi",
        "ok" if not loose else f"troppo aperti (chmod 600): {', '.join(loose[:5])}",
        warn_only=True,
    )
    check(
        selector.is_available(),
        "terminale",
        "interattivo (TTY)" if selector.is_available() else "non interattivo",
        warn_only=True,
    )
    check(True, "tema", theme.active_mode())
    check(True, "interfaccia", ui_mode())

    if problems:
        ui.print_error(f"{problems} problema/i da risolvere.")
        return 1
    ui.print_success("Tutto ok!")
    return 0


# -------------------------------------------------------------- dashboard --


def dashboard_loop(instances: dict[str, store.SSHInstance]) -> str:
    """Drive the dashboard: run the action it returns, then re-enter.

    Returns "menu" (switch to the classic menu) or "quit".
    """
    health_cache: dict[str, health.Status] = {}
    while True:
        action, name = dashboard.run(instances, health_cache)
        if action in ("quit", "menu"):
            return action
        if action == "connect" and name:
            if connect_by_name(instances, name) != 0:
                ui.pause()
            continue
        if action == "edit" and name:
            edit_interactive(instances, name=name)
        elif action == "delete" and name:
            delete_interactive(instances, name=name)
            health_cache.pop(name, None)
        elif action == "new":
            add_interactive(instances)
        elif action == "import":
            import_ssh_config_interactive(instances)
        else:
            continue
        ui.pause()
