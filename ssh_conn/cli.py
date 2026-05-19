"""Typer-based CLI entry point. No args → interactive loop."""
from __future__ import annotations

import sys
from typing import Optional

import typer

from . import commands, health, ui

app = typer.Typer(
    help="SSH Connection Manager — gestione istanze SSH.",
    no_args_is_help=False,
    add_completion=True,
)

_MENU_DISPATCH = {
    "1": commands.list_interactive,
    "2": commands.connect_interactive,
    "3": commands.add_interactive,
    "4": commands.edit_interactive,
    "5": commands.delete_interactive,
    "6": commands.health_view,
    "7": commands.import_ssh_config_interactive,
}


def _interactive_loop() -> int:
    try:
        instances = commands.load()
    except (OSError, ValueError) as exc:
        ui.print_error(f"Impossibile caricare {commands.config_path()}: {exc}")
        return 1

    ui.clear_screen()
    while True:
        ui.render_main_menu()
        choice = ui.prompt_menu_choice(("1", "2", "3", "4", "5", "6", "7", "q"))
        if choice is None or choice == "q":
            ui.print_warning("Arrivederci!")
            return 0
        if choice == "":
            ui.print_error("Scelta non valida.")
            continue
        _MENU_DISPATCH[choice](instances)


@app.callback(invoke_without_command=True)
def _default(
    ctx: typer.Context,
    config: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path al file di config (override env/default)."
    ),
) -> None:
    commands.set_config_path(config)
    if ctx.invoked_subcommand is None:
        raise typer.Exit(code=_interactive_loop())


@app.command("connect", help="Connetti a un'istanza per nome (match fuzzy).")
def cmd_connect(
    name: str = typer.Argument(..., help="Nome o substring dell'istanza."),
) -> None:
    instances = commands.load()
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
    name: str = typer.Argument(..., help="Nome dell'istanza."),
) -> None:
    instances = commands.load()
    resolved = commands.resolve_name(instances, name)
    if not resolved:
        raise typer.Exit(code=1)
    commands.edit_interactive(instances, name=resolved)


@app.command("delete", help="Elimina un'istanza esistente.")
def cmd_delete(
    name: str = typer.Argument(..., help="Nome dell'istanza."),
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
    ui.print_info(f"Health check in corso su {len(filtered)} istanze...")
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


def run() -> None:
    sys.exit(app() or 0)


if __name__ == "__main__":
    run()
