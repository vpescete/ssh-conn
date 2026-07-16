"""UI layer: rich rendering and prompt_toolkit input helpers."""
from __future__ import annotations

from typing import Iterable

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import FuzzyCompleter, WordCompleter
from prompt_toolkit.styles import Style as PTStyle
from rich.console import Console
from rich.table import Table
from rich.text import Text

from . import history, selector, theme
from .health import Status
from .store import SSHInstance

console = Console()


def health_glyph(status: Status) -> str:
    """Health dot with a distinct shape (not only colour) for accessibility."""
    palette = theme.active_palette()
    return {
        True: f"[{palette.health_ok}]✓[/]",
        False: f"[{palette.health_bad}]✗[/]",
        None: f"[{palette.health_timeout}]?[/]",
    }.get(status, "")


GROUP_ICONS: dict[str, str] = {
    "OVH": "☁️",
    "GCP": "🌐",
    "CL": "🔷",
    "OVS": "🟣",
    "Odoo": "🟡",
    "Buyprotect": "🛒",
    "other": "📦",
}

_GROUP_ORDER: tuple[str, ...] = ("OVH", "GCP", "CL", "OVS", "Odoo", "Buyprotect", "other")

_session: PromptSession = PromptSession()
_pt_style = PTStyle.from_dict({"prompt": "ansicyan bold"})


def clear_screen() -> None:
    console.clear()


def status(message: str):
    """Context manager showing an animated spinner around a blocking task."""
    return console.status(f"[{theme.active_palette().accent}]{message}[/]", spinner="dots")


def pause(message: str = "⏎  Premi Invio per continuare...") -> None:
    try:
        _session.prompt(f"\n{message} ")
    except (KeyboardInterrupt, EOFError):
        return


def format_ssh_command(instance: SSHInstance) -> str:
    parts: list[str] = ["ssh"]
    if instance.port != 22:
        parts += ["-p", str(instance.port)]
    if instance.key_path:
        parts += ["-i", instance.key_path]
    parts.append(f"{instance.username}@{instance.hostname}")
    return " ".join(parts)


def _print_with_icon(icon: str, style: str, message: str) -> None:
    lead = ""
    while message.startswith("\n"):
        lead += "\n"
        message = message[1:]
    console.print(f"{lead}[{style}]{icon} {message}[/{style}]")


def print_info(message: str) -> None:
    _print_with_icon("ℹ️", theme.active_palette().accent, message)


def print_success(message: str) -> None:
    _print_with_icon("✅", theme.active_palette().health_ok, message)


def print_warning(message: str) -> None:
    _print_with_icon("⚠️", theme.active_palette().health_timeout, message)


def print_error(message: str) -> None:
    _print_with_icon("❌", theme.active_palette().health_bad, message)


def goodbye() -> None:
    console.print(f"\n[bold {theme.active_palette().accent}]👋 Arrivederci![/]\n")


def print_connecting(name: str, command: str) -> None:
    palette = theme.active_palette()
    console.print(f"[bold {palette.health_ok}]🔌 Connessione a[/] [bold]{name}[/] …")
    console.print(f"[{palette.muted}]$ {command}[/]")


def print_ssh_command(instance: SSHInstance) -> None:
    palette = theme.active_palette()
    console.print(
        f"[{palette.accent}]🔗 Comando SSH equivalente:[/] "
        f"[{palette.health_timeout}]{format_ssh_command(instance)}[/]"
    )


def _menu_options(last_name: str | None) -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = []
    if last_name:
        options.append(("0", f"🔁 Riconnetti all'ultimo ({last_name})"))
    options += [
        ("1", "📋 Lista istanze"),
        ("2", "🔌 Connetti a istanza"),
        ("3", "➕ Aggiungi istanza"),
        ("4", "✏️  Modifica istanza"),
        ("5", "🗑️  Elimina istanza"),
        ("6", "🩺 Health check"),
        ("7", "📥 Importa da ~/.ssh/config"),
        ("d", "🧭 Dashboard (interfaccia a schermo intero)"),
        ("q", "🚪 Esci"),
    ]
    return options


def render_main_menu(last_name: str | None = None, subtitle: str | None = None) -> None:
    menu = Text()
    menu.append("\n🔐 SSH Connection Manager\n", style=f"bold {theme.active_palette().accent}")
    if subtitle:
        menu.append(f"{subtitle}\n", style=theme.active_palette().muted)
    menu.append("\n")
    for key, label in _menu_options(last_name):
        menu.append(f"  {key}. ", style="bold")
        menu.append(f"{label}\n")
    console.print(menu)


def main_menu(last_name: str | None = None, subtitle: str | None = None) -> str | None:
    """Return the chosen menu key. Navigable on a TTY, typed prompt otherwise."""
    options = _menu_options(last_name)
    if selector.is_available():
        choice = selector.menu_select(
            options, title="🔐 SSH Connection Manager", subtitle=subtitle
        )
        return "q" if choice is None else choice
    render_main_menu(last_name=last_name, subtitle=subtitle)
    return prompt_menu_choice(tuple(key for key, _ in options))


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


def ordered_names(instances: dict[str, SSHInstance]) -> list[str]:
    """Names in the exact order the grouped table renders them.

    Used to map the '#' column shown by render_instance_table back to a name.
    """
    grouped: dict[str, list[SSHInstance]] = {}
    for inst in instances.values():
        grouped.setdefault(inst.group, []).append(inst)
    names: list[str] = []
    for group in _sort_groups(grouped.keys()):
        for inst in sorted(grouped[group], key=lambda i: i.name.lower()):
            names.append(inst.name)
    return names


def render_recents(
    instances: dict[str, SSHInstance],
    limit: int = 5,
    health: dict[str, Status] | None = None,
) -> None:
    recent = history.recent_names(known=set(instances.keys()), limit=limit)
    if not recent:
        return
    palette = theme.active_palette()
    table = Table(
        title=f"[bold {palette.recent}]⏱️  Recenti[/] [{palette.muted}](ultimi accessi)[/]",
        header_style=f"bold {palette.recent}",
        border_style=palette.recent,
        title_justify="left",
        show_lines=False,
    )
    table.add_column("●" if health else "", justify="center")
    table.add_column("Nome", style=palette.text)
    table.add_column("Host", style=palette.muted)
    table.add_column("User", style=palette.muted)
    table.add_column("Quando", style=palette.recent)
    for name in recent:
        inst = instances[name]
        ago = history.time_ago(history.last_access(name) or "")
        glyph = health_glyph(health.get(name)) if health else ""
        table.add_row(glyph or "", name, inst.hostname, inst.username, ago)
    console.print(table)
    console.print("")


def render_instance_table(
    instances: dict[str, SSHInstance],
    health: dict[str, Status] | None = None,
    show_recents: bool = True,
    show_numbers: bool = False,
    empty_message: str | None = None,
) -> None:
    palette = theme.active_palette()
    if not instances:
        console.print(
            f"[{palette.health_timeout}]{empty_message or 'Nessuna istanza configurata.'}[/]"
        )
        return

    if show_recents:
        render_recents(instances, health=health)

    number_map: dict[str, int] = {}
    if show_numbers:
        number_map = {name: i for i, name in enumerate(ordered_names(instances), start=1)}

    grouped: dict[str, list[SSHInstance]] = {}
    for inst in instances.values():
        grouped.setdefault(inst.group, []).append(inst)

    for group in _sort_groups(grouped.keys()):
        members = sorted(grouped[group], key=lambda i: i.name.lower())
        color = palette.group_colors.get(group, palette.text)
        icon = GROUP_ICONS.get(group, "📦")
        table = Table(
            title=f"[bold {color}]{icon} {group}[/] [{palette.muted}]({len(members)})[/]",
            header_style=f"bold {color}",
            border_style=color,
            title_justify="left",
            show_lines=False,
        )
        if show_numbers:
            table.add_column("#", justify="right", style="bold")
        if health is not None:
            table.add_column("St", justify="center")
        table.add_column("Nome", style=palette.text)
        table.add_column("Host", style=palette.muted)
        table.add_column("User", style=palette.muted)
        table.add_column("Tags", style=color)
        table.add_column("Porta", justify="right", style=palette.muted)
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
                row.insert(0, health_glyph(health.get(inst.name)))
            if show_numbers:
                row.insert(0, str(number_map[inst.name]))
            table.add_row(*row)
        console.print(table)
        console.print("")

    total = sum(len(v) for v in grouped.values())
    summary = " · ".join(
        f"[bold]{g}[/]: {len(grouped[g])}" for g in _sort_groups(grouped.keys())
    )
    console.print(f"[{palette.muted}]Totale {total} istanze · {summary}[/]")
    if health is not None:
        up = sum(1 for v in health.values() if v is True)
        down = sum(1 for v in health.values() if v is False)
        timeout = sum(1 for v in health.values() if v is None)
        console.print(
            f"[{palette.muted}]Reachability:[/] [{palette.health_ok}]✓[/] {up} · "
            f"[{palette.health_bad}]✗[/] {down} · [{palette.health_timeout}]?[/] {timeout}"
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
    palette = theme.active_palette()
    if not instances:
        console.print(f"[{palette.health_timeout}]Nessuna istanza disponibile.[/]")
        return None
    names = sorted(instances.keys())
    if selector.is_available():
        try:
            # None here means the user cancelled — honour it, don't fall through.
            return selector.fuzzy_select(names, prompt_label=prompt_label)
        except Exception as exc:  # noqa: BLE001 — degrade to the typed prompt below
            console.print(
                f"[{palette.muted}]Selettore interattivo non disponibile ({exc}); uso input testuale.[/]"
            )
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
            f"[{palette.health_timeout}]Match ambiguo per '{query}':[/] "
            f"{', '.join(substring_matches[:5])}"
        )
        return None
    console.print(f"[{palette.health_bad}]Nessuna istanza trovata per '{query}'.[/]")
    return None
