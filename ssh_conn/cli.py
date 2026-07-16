"""Typer-based CLI entry point. No args → interactive loop."""
from __future__ import annotations

import os
import sys
from typing import Optional

import typer

from . import __version__, commands, health, selector, settings, theme, ui

app = typer.Typer(
    help="SSH Connection Manager — gestione istanze SSH.",
    no_args_is_help=False,
    add_completion=True,
)

_MENU_DISPATCH = {
    "0": commands.connect_last,
    "1": commands.list_interactive,
    "2": commands.connect_interactive,
    "3": commands.add_interactive,
    "4": commands.edit_interactive,
    "5": commands.delete_interactive,
    "6": commands.health_view,
    "7": commands.import_ssh_config_interactive,
}


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"ssh-conn {__version__}")
        raise typer.Exit()


def _complete_instance_names(incomplete: str) -> list[str]:
    """Shell completion: match configured instance names (failure-tolerant)."""
    try:
        instances = commands.load()
    except (OSError, ValueError):
        return []
    return [name for name in instances if incomplete.lower() in name.lower()]


def _maybe_save_ui_default() -> None:
    """After the user tries the dashboard, offer once to persist a preference."""
    if settings.ui_preference() is not None:
        return
    if commands.has_ui_override() or os.environ.get("SSH_CONN_UI"):
        return
    if ui.prompt_confirm(
        "Impostare la dashboard come interfaccia predefinita?", default=False
    ):
        saved = settings.save_setting("ui", "dashboard")
        message = "Dashboard predefinita (torna al menu con: ssh-conn ui menu)."
    else:
        saved = settings.save_setting("ui", "menu")
        message = "Resta il menu classico (dashboard con la voce 'd' o --ui dashboard)."
    if saved:
        ui.print_info(message)


def _interactive_loop() -> int:
    try:
        instances = commands.load()
    except (OSError, ValueError) as exc:
        ui.print_error(f"Impossibile caricare {commands.config_path()}: {exc}")
        return 1

    mode = commands.ui_mode()
    while True:
        if mode == "dashboard":
            if not selector.is_available():
                ui.print_warning(
                    "La dashboard richiede un terminale interattivo; uso il menu classico."
                )
                mode = "menu"
                continue
            outcome = commands.dashboard_loop(instances)
            _maybe_save_ui_default()
            if outcome == "menu":
                mode = "menu"
                continue
            ui.goodbye()
            return 0

        ui.clear_screen()
        last = commands.last_used_name(instances)
        subtitle = (
            f"{len(instances)} istanze · tema {theme.active_mode()} · "
            f"config: {commands.config_path()}"
        )
        choice = ui.main_menu(last_name=last, subtitle=subtitle)
        if choice is None or choice == "q":
            ui.goodbye()
            return 0
        if choice == "d":
            mode = "dashboard"
            continue
        if choice == "":
            ui.print_error("Scelta non valida.")
            ui.pause()
            continue
        _MENU_DISPATCH[choice](instances)
        ui.pause()


@app.callback(invoke_without_command=True)
def _default(
    ctx: typer.Context,
    config: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path al file di config (override env/default)."
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Mostra la versione ed esci.",
    ),
    theme_opt: Optional[str] = typer.Option(
        None, "--theme", help="Forza il tema colori: dark | light | auto (default: auto)."
    ),
    ui_opt: Optional[str] = typer.Option(
        None, "--ui", help="Interfaccia interattiva: menu | dashboard."
    ),
) -> None:
    normalized_ui = ui_opt.strip().lower() if ui_opt else None
    if normalized_ui is not None and normalized_ui not in commands.VALID_UI:
        ui.print_error(f"Valore --ui non valido: '{ui_opt}' (usa: menu | dashboard).")
        raise typer.Exit(code=2)
    theme.set_theme(theme_opt)
    commands.set_ui_mode(normalized_ui)
    commands.set_config_path(config)
    commands.migrate_legacy_config()
    if ctx.invoked_subcommand is None:
        raise typer.Exit(code=_interactive_loop())


@app.command("connect", help="Connetti a un'istanza (match fuzzy); senza nome riprende l'ultima.")
def cmd_connect(
    name: Optional[str] = typer.Argument(
        None,
        help="Nome o substring; se omesso riconnette all'ultima usata.",
        autocompletion=_complete_instance_names,
    ),
) -> None:
    instances = commands.load()
    if not name:
        raise typer.Exit(code=commands.connect_last(instances))
    resolved = commands.resolve_name(instances, name)
    if not resolved:
        raise typer.Exit(code=1)
    code = commands.connect_by_name(instances, resolved)
    raise typer.Exit(code=code)


@app.command("list", help="Elenca le istanze, opzionalmente filtrate.")
def cmd_list(
    filters: Optional[list[str]] = typer.Argument(
        None, help="Termini di filtro (es. 'ovh prod')."
    ),
    with_health: bool = typer.Option(
        False, "--health", "-H", help="Esegui health check parallelo."
    ),
) -> None:
    instances = commands.load()
    commands.list_view(instances, filters or [], check_health=with_health)


@app.command("add", help="Aggiungi una nuova istanza (interattivo).")
def cmd_add() -> None:
    instances = commands.load()
    commands.add_interactive(instances)


@app.command("edit", help="Modifica un'istanza esistente.")
def cmd_edit(
    name: str = typer.Argument(
        ..., help="Nome dell'istanza.", autocompletion=_complete_instance_names
    ),
) -> None:
    instances = commands.load()
    resolved = commands.resolve_name(instances, name)
    if not resolved:
        raise typer.Exit(code=1)
    commands.edit_interactive(instances, name=resolved)


@app.command("delete", help="Elimina un'istanza esistente.")
def cmd_delete(
    name: str = typer.Argument(
        ..., help="Nome dell'istanza.", autocompletion=_complete_instance_names
    ),
) -> None:
    instances = commands.load()
    resolved = commands.resolve_name(instances, name)
    if not resolved:
        raise typer.Exit(code=1)
    commands.delete_interactive(instances, name=resolved)


@app.command("health", help="Health check parallelo (TCP) su tutte le istanze.")
def cmd_health(
    filters: Optional[list[str]] = typer.Argument(
        None, help="Filtri opzionali."
    ),
) -> None:
    instances = commands.load()
    filtered = ui.filter_instances(instances, filters or [])
    if not filtered:
        ui.print_warning("Nessuna istanza dopo i filtri.")
        raise typer.Exit(code=0)
    with ui.status(f"🩺 Health check su {len(filtered)} istanze..."):
        results = health.check_reachability(filtered)
    ui.render_instance_table(filtered, health=results)


@app.command("import-ssh", help="Importa istanze da un file ssh config.")
def cmd_import(
    source: str = typer.Option(
        "~/.ssh/config", "--source", "-s", help="File ssh config sorgente."
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Sovrascrivi istanze già presenti."
    ),
) -> None:
    instances = commands.load()
    added, skipped = commands.import_ssh_config(
        instances, source=source, overwrite=overwrite
    )
    if added == 0 and skipped > 0:
        raise typer.Exit(code=0)


@app.command("config-path", help="Stampa il path della config attualmente in uso.")
def cmd_config_path() -> None:
    typer.echo(str(commands.config_path()))


@app.command("restore", help="Ripristina l'ultima istanza eliminata.")
def cmd_restore() -> None:
    instances = commands.load()
    raise typer.Exit(code=commands.restore_last(instances))


@app.command("doctor", help="Diagnostica ambiente e configurazione.")
def cmd_doctor() -> None:
    raise typer.Exit(code=commands.doctor())


@app.command("ui", help="Mostra o imposta l'interfaccia predefinita (menu | dashboard).")
def cmd_ui(
    mode: Optional[str] = typer.Argument(
        None, help="menu | dashboard (vuoto: mostra quella attiva)."
    ),
) -> None:
    if mode is None:
        typer.echo(commands.ui_mode())
        return
    normalized = mode.strip().lower()
    if normalized not in commands.VALID_UI:
        ui.print_error(f"Valore non valido: '{mode}' (usa: menu | dashboard).")
        raise typer.Exit(code=2)
    if not settings.save_setting("ui", normalized):
        ui.print_error("Impossibile salvare le impostazioni.")
        raise typer.Exit(code=1)
    ui.print_success(f"Interfaccia predefinita: {normalized}")


def run() -> None:
    sys.exit(app() or 0)


if __name__ == "__main__":
    run()
