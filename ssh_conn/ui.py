"""UI layer: rich rendering and prompt_toolkit input helpers."""
from __future__ import annotations

from typing import Iterable

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import FuzzyCompleter, WordCompleter
from prompt_toolkit.styles import Style as PTStyle
from rich.console import Console
from rich.table import Table
from rich.text import Text

from . import history
from .health import Status
from .store import SSHInstance

HEALTH_GLYPHS: dict[Status, str] = {
    True: "[green]●[/green]",
    False: "[red]●[/red]",
    None: "[yellow]●[/yellow]",
}

console = Console()

GROUP_COLORS: dict[str, str] = {
    "OVH": "green",
    "GCP": "blue",
    "CL": "cyan",
    "OVS": "magenta",
    "Odoo": "yellow",
    "Buyprotect": "red",
    "other": "white",
}

_GROUP_ORDER: tuple[str, ...] = ("OVH", "GCP", "CL", "OVS", "Odoo", "Buyprotect", "other")

_session: PromptSession = PromptSession()
_pt_style = PTStyle.from_dict({"prompt": "ansicyan bold"})


def clear_screen() -> None:
    console.clear()


def format_ssh_command(instance: SSHInstance) -> str:
    parts: list[str] = ["ssh"]
    if instance.port != 22:
        parts += ["-p", str(instance.port)]
    if instance.key_path:
        parts += ["-i", instance.key_path]
    parts.append(f"{instance.username}@{instance.hostname}")
    return " ".join(parts)


def print_info(message: str) -> None:
    console.print(f"[cyan]{message}[/cyan]")


def print_success(message: str) -> None:
    console.print(f"[green]{message}[/green]")


def print_warning(message: str) -> None:
    console.print(f"[yellow]{message}[/yellow]")


def print_error(message: str) -> None:
    console.print(f"[red]{message}[/red]")


def print_ssh_command(instance: SSHInstance) -> None:
    console.print(
        f"[cyan]Comando SSH equivalente:[/cyan] "
        f"[yellow]{format_ssh_command(instance)}[/yellow]"
    )


def render_main_menu() -> None:
    menu = Text()
    menu.append("\n=== SSH Connection Manager ===\n\n", style="bold cyan")
    options = (
        ("1", "Lista istanze"),
        ("2", "Connetti a istanza"),
        ("3", "Aggiungi istanza"),
        ("4", "Modifica istanza"),
        ("5", "Elimina istanza"),
        ("6", "Health check"),
        ("7", "Importa da ~/.ssh/config"),
        ("q", "Esci"),
    )
    for key, label in options:
        menu.append(f"  {key}. ", style="bold")
        menu.append(f"{label}\n")
    console.print(menu)


def filter_instances(
    instances: dict[str, SSHInstance], terms: Iterable[str]
) -> dict[str, SSHInstance]:
    terms_lc = [t.lower() for t in terms if t]
    if not terms_lc:
        return dict(instances)
    result: dict[str, SSHInstance] = {}
    for name, inst in instances.items():
        haystack = " ".join(
            [
                name.lower(),
                inst.hostname.lower(),
                inst.username.lower(),
                inst.group.lower(),
                " ".join(inst.tags),
            ]
        )
        if all(t in haystack for t in terms_lc):
            result[name] = inst
    return result


def _sort_groups(groups: Iterable[str]) -> list[str]:
    def key(g: str) -> int:
        return _GROUP_ORDER.index(g) if g in _GROUP_ORDER else len(_GROUP_ORDER)

    return sorted(set(groups), key=key)


def render_recents(
    instances: dict[str, SSHInstance],
    limit: int = 5,
    health: dict[str, Status] | None = None,
) -> None:
    recent = history.recent_names(known=set(instances.keys()), limit=limit)
    if not recent:
        return
    table = Table(
        title="[bold magenta]Recenti[/] [dim](ultimi accessi)[/]",
        header_style="bold magenta",
        border_style="magenta",
        title_justify="left",
        show_lines=False,
    )
    table.add_column("●" if health else "", justify="center")
    table.add_column("Nome", style="white")
    table.add_column("Host", style="dim")
    table.add_column("User", style="dim")
    table.add_column("Quando", style="magenta")
    for name in recent:
        inst = instances[name]
        ago = history.time_ago(history.last_access(name) or "")
        glyph = HEALTH_GLYPHS.get(health.get(name)) if health else ""
        table.add_row(glyph or "", name, inst.hostname, inst.username, ago)
    console.print(table)
    console.print("")


def render_instance_table(
    instances: dict[str, SSHInstance],
    health: dict[str, Status] | None = None,
    show_recents: bool = True,
) -> None:
    if not instances:
        console.print("[yellow]Nessuna istanza configurata.[/yellow]")
        return

    if show_recents:
        render_recents(instances, health=health)

    grouped: dict[str, list[SSHInstance]] = {}
    for inst in instances.values():
        grouped.setdefault(inst.group, []).append(inst)

    for group in _sort_groups(grouped.keys()):
        members = sorted(grouped[group], key=lambda i: i.name.lower())
        color = GROUP_COLORS.get(group, "white")
        table = Table(
            title=f"[bold {color}]{group}[/] [dim]({len(members)})[/]",
            header_style=f"bold {color}",
            border_style=color,
            title_justify="left",
            show_lines=False,
        )
        if health is not None:
            table.add_column("●", justify="center")
        table.add_column("Nome", style="white")
        table.add_column("Host", style="dim")
        table.add_column("User", style="dim")
        table.add_column("Tags", style=color)
        table.add_column("Porta", justify="right", style="dim")
        table.add_column("Key", justify="center")
        for inst in members:
            tags_str = " ".join(inst.tags[:5])
            port_str = "" if inst.port == 22 else str(inst.port)
            key_marker = "✓" if inst.key_path else "—"
            row = [
                inst.name,
                inst.hostname,
                inst.username,
                tags_str,
                port_str,
                key_marker,
            ]
            if health is not None:
                row.insert(0, HEALTH_GLYPHS.get(health.get(inst.name), ""))
            table.add_row(*row)
        console.print(table)
        console.print("")

    total = sum(len(v) for v in grouped.values())
    summary = " · ".join(
        f"[bold]{g}[/]: {len(grouped[g])}" for g in _sort_groups(grouped.keys())
    )
    console.print(f"[dim]Totale {total} istanze · {summary}[/]")
    if health is not None:
        up = sum(1 for v in health.values() if v is True)
        down = sum(1 for v in health.values() if v is False)
        timeout = sum(1 for v in health.values() if v is None)
        console.print(
            f"[dim]Reachability:[/] [green]●[/] {up} · "
            f"[red]●[/] {down} · [yellow]●[/] {timeout}"
        )


def prompt_text(message: str, default: str = "") -> str | None:
    """Required text prompt. Returns stripped string, None on cancel, empty string treated as cancel."""
    try:
        result = _session.prompt(f"{message}: ", default=default, style=_pt_style)
    except (KeyboardInterrupt, EOFError):
        return None
    return result.strip() or None


def prompt_optional(message: str, default: str = "") -> str | None:
    """Optional text prompt with editable default. Returns stripped string (may be empty) or None on cancel."""
    try:
        result = _session.prompt(f"{message}: ", default=default, style=_pt_style)
    except (KeyboardInterrupt, EOFError):
        return None
    return result.strip()


def prompt_confirm(message: str, default: bool = False) -> bool:
    suffix = "S/n" if default else "s/N"
    try:
        ans = _session.prompt(f"{message} [{suffix}]: ", style=_pt_style).strip().lower()
    except (KeyboardInterrupt, EOFError):
        return False
    if not ans:
        return default
    return ans in ("s", "si", "y", "yes")


def prompt_menu_choice(valid: tuple[str, ...]) -> str | None:
    try:
        choice = _session.prompt("→ scelta: ", style=_pt_style).strip().lower()
    except (KeyboardInterrupt, EOFError):
        return None
    if choice in valid:
        return choice
    return ""


def select_instance_fuzzy(
    instances: dict[str, SSHInstance], prompt_label: str = "Cerca istanza"
) -> str | None:
    if not instances:
        console.print("[yellow]Nessuna istanza disponibile.[/yellow]")
        return None
    names = sorted(instances.keys())
    completer = FuzzyCompleter(WordCompleter(names, match_middle=True, ignore_case=True))
    try:
        raw = _session.prompt(
            f"{prompt_label} (Tab per autocomplete, Invio vuoto per annullare): ",
            completer=completer,
            complete_while_typing=True,
            style=_pt_style,
        )
    except (KeyboardInterrupt, EOFError):
        return None
    query = raw.strip()
    if not query:
        return None
    if query in instances:
        return query
    lower_map = {n.lower(): n for n in names}
    if query.lower() in lower_map:
        return lower_map[query.lower()]
    substring_matches = [n for n in names if query.lower() in n.lower()]
    if len(substring_matches) == 1:
        return substring_matches[0]
    if len(substring_matches) > 1:
        console.print(
            f"[yellow]Match ambiguo per '{query}':[/yellow] "
            f"{', '.join(substring_matches[:5])}"
        )
        return None
    console.print(f"[red]Nessuna istanza trovata per '{query}'.[/red]")
    return None
