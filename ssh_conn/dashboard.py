"""Full-screen dashboard: one surface to browse, filter and act on instances.

Exit-and-reenter pattern: the dashboard never runs business logic itself.
Every action exits the prompt_toolkit Application returning an
``(action, payload)`` tuple; the driver (``commands.dashboard_loop``) executes
it in normal terminal mode, then re-enters the dashboard. Live health results
accumulate in the ``health_state`` dict shared across re-entries.
"""
from __future__ import annotations

import shutil
import subprocess

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import (
    ConditionalContainer,
    Float,
    FloatContainer,
    HSplit,
    VSplit,
    Window,
)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame

from . import health as health_mod
from . import history, selector, theme
from .store import SSHInstance
from .ui import GROUP_ICONS, format_ssh_command

_NAME_WIDTH = 30
_TARGET_WIDTH = 28
_GROUP_WIDTH = 12
_RECENCY_WIDTH = 8
_CHROME_ROWS = 4          # header + search + keybar + margin
_MIN_LIST_ROWS = 3
_MAX_LIST_ROWS = 40
_PREVIEW_MIN_COLS = 96    # hide the detail pane on narrower terminals

# ANSI colours adapt to the terminal palette, so both themes stay legible.
_GROUP_STYLES: dict[str, str] = {
    "OVH": "ansigreen",
    "GCP": "ansiblue",
    "CL": "ansicyan",
    "OVS": "ansimagenta",
    "Odoo": "ansiyellow",
    "Buyprotect": "ansired",
    "other": "",
}

def _build_style() -> Style:
    """Built at app time so 'muted' uses the active theme's readable grey."""
    return Style.from_dict(
        {
            "header": "ansicyan bold",
            "muted": theme.active_palette().muted,
            "selected": "reverse",
            "match": "ansicyan bold",
            "ok": "ansigreen",
            "bad": "ansired",
            "tmo": "ansiyellow",
            "label": "ansicyan bold",
            "message": "ansigreen",
        }
    )

_HEALTH_RUNNING_MESSAGE = "🩺 Health check in corso…"

_HELP_KEYS: tuple[tuple[str, str], ...] = (
    ("⏎", "connetti all'istanza selezionata"),
    ("↑ ↓", "naviga · PgSu/PgGiù salta"),
    ("testo", "filtra (fuzzy, come fzf)"),
    ("Ctrl-E", "modifica o rinomina selezionata"),
    ("Ctrl-D", "elimina selezionata"),
    ("Ctrl-N", "nuova istanza"),
    ("Ctrl-T", "(ri)esegui health check"),
    ("Ctrl-Y", "copia comando ssh"),
    ("Ctrl-O", "pannello dettagli on/off"),
    ("F3", "importa da ~/.ssh/config"),
    ("F2", "passa al menu classico"),
    ("F1", "apri/chiudi questo aiuto"),
    ("Esc", "svuota filtro / esci"),
)

_CLIPBOARD_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("pbcopy",),
    ("xclip", "-selection", "clipboard"),
    ("xsel", "--clipboard", "--input"),
)


def _fit(text: str, width: int) -> str:
    if len(text) <= width:
        return text.ljust(width)
    return text[: width - 1] + "…"


def _style(*parts: str) -> str:
    return " ".join(p for p in parts if p)


def _copy_to_clipboard(text: str) -> bool:
    for command in _CLIPBOARD_COMMANDS:
        if not shutil.which(command[0]):
            continue
        try:
            subprocess.run(list(command), input=text.encode(), check=True)
            return True
        except (OSError, subprocess.CalledProcessError):
            continue
    return False


def ranked_matches(
    names: list[str], query: str, scores: dict[str, float]
) -> list[tuple[str, list[int]]]:
    """(name, matched positions) — frecency order when idle, fuzzy when filtering."""
    stripped = query.strip().lower()
    if not stripped:
        ordered = sorted(names, key=lambda n: (-scores.get(n, 0.0), n.lower()))
        return [(n, []) for n in ordered]
    ranked: list[tuple[tuple, str, list[int]]] = []
    for name in names:
        positions = selector.subsequence_positions(stripped, name.lower())
        if positions is None:
            continue
        span = positions[-1] - positions[0]
        key = (span, positions[0], -scores.get(name, 0.0), name.lower())
        ranked.append((key, name, positions))
    ranked.sort(key=lambda item: item[0])
    return [(name, positions) for _, name, positions in ranked]


class _Dashboard:
    def __init__(
        self,
        instances: dict[str, SSHInstance],
        health_state: dict[str, health_mod.Status],
        start_query: str = "",
    ) -> None:
        self.instances = instances
        self.health = health_state
        self.scores = history.frecency_scores()
        self.recency = {
            name: history.time_ago(entry["last"])
            for name, entry in history.load_history().items()
        }
        self.buffer = Buffer(
            multiline=False,
            document=Document(text=start_query, cursor_position=len(start_query)),
        )
        self.buffer.on_text_changed += self._on_text_changed
        self.state: dict[str, object] = {
            "selected": 0,
            "preview": True,
            "help": False,
            "message": "",
        }

    def _on_text_changed(self, _buffer: Buffer) -> None:
        self.state["selected"] = 0
        if str(self.state["message"]) != _HEALTH_RUNNING_MESSAGE:
            self.state["message"] = ""

    # ------------------------------------------------------------- data --

    def matches(self) -> list[tuple[str, list[int]]]:
        result = ranked_matches(list(self.instances), self.buffer.text, self.scores)
        last = max(0, len(result) - 1)
        self.state["selected"] = min(max(int(self.state["selected"]), 0), last)
        return result

    def selected_name(self) -> str | None:
        matches = self.matches()
        return matches[int(self.state["selected"])][0] if matches else None

    def visible_rows(self) -> int:
        rows = get_app().output.get_size().rows - _CHROME_ROWS
        return max(_MIN_LIST_ROWS, min(rows, _MAX_LIST_ROWS))

    async def _health_task(self, app: Application) -> None:
        pending = {n: i for n, i in self.instances.items() if n not in self.health}
        if not pending:
            return

        def on_result(name: str, status: health_mod.Status) -> None:
            self.health[name] = status
            app.invalidate()

        await health_mod.check_streaming(pending, on_result)
        if str(self.state["message"]) == _HEALTH_RUNNING_MESSAGE:
            self.state["message"] = ""
        app.invalidate()

    # -------------------------------------------------------- fragments --

    def _health_fragment(self, name: str, selected_style: str) -> tuple[str, str]:
        if name not in self.health:
            return (_style("class:muted", selected_style), "· ")
        style, glyph = {
            True: ("class:ok", "✓ "),
            False: ("class:bad", "✗ "),
            None: ("class:tmo", "? "),
        }[self.health[name]]
        return (_style(style, selected_style), glyph)

    def _row_fragments(self, name: str, positions: list[int], is_selected: bool) -> list:
        inst = self.instances[name]
        sel = "class:selected" if is_selected else ""
        fragments: list = [(_style("class:label", sel), "› " if is_selected else "  ")]
        fragments.append(self._health_fragment(name, sel))
        shown = name if len(name) <= _NAME_WIDTH else name[: _NAME_WIDTH - 1] + "…"
        matched = set(positions)
        for index, char in enumerate(shown):
            fragments.append((_style("class:match" if index in matched else "", sel), char))
        fragments.append((sel, " " * (_NAME_WIDTH - len(shown) + 1)))
        target = _fit(f"{inst.username}@{inst.hostname}", _TARGET_WIDTH)
        fragments.append((_style("class:muted", sel), target + " "))
        group_style = _GROUP_STYLES.get(inst.group, "")
        fragments.append((_style(group_style, sel), _fit(inst.group, _GROUP_WIDTH) + " "))
        recency = _fit(self.recency.get(name, "—"), _RECENCY_WIDTH)
        fragments.append((_style("class:muted", sel), recency))
        fragments.append(("", "\n"))
        return fragments

    def list_fragments(self) -> list:
        if not self.instances:
            return [
                ("class:muted", "\n  Nessuna istanza configurata.\n\n"),
                ("class:label", "  Ctrl-N"),
                ("", " aggiungi la prima istanza · "),
                ("class:label", "F3"),
                ("", " importa da ~/.ssh/config\n"),
            ]
        matches = self.matches()
        if not matches:
            return [("class:muted", "\n  (nessun risultato per il filtro)\n")]
        selected = int(self.state["selected"])
        rows = self.visible_rows()
        start = selector.window_start(len(matches), selected, rows)
        fragments: list = []
        for index in range(start, min(start + rows, len(matches))):
            name, positions = matches[index]
            fragments.extend(self._row_fragments(name, positions, index == selected))
        return fragments

    def preview_fragments(self) -> list:
        name = self.selected_name()
        if not name:
            return [("class:muted", " (nessuna selezione)")]
        inst = self.instances[name]
        if name in self.health:
            status = self.health[name]
            state_style, state_text = {
                True: ("class:ok", "✓ raggiungibile"),
                False: ("class:bad", "✗ non raggiungibile"),
                None: ("class:tmo", "? timeout"),
            }[status]
        else:
            state_style, state_text = ("class:muted", "· in verifica…")
        icon = GROUP_ICONS.get(inst.group, "📦")
        return [
            ("class:header", f" {name}\n\n"),
            ("class:muted", " host    "), ("", f"{inst.hostname}\n"),
            ("class:muted", " user    "), ("", f"{inst.username}\n"),
            ("class:muted", " porta   "), ("", f"{inst.port}\n"),
            ("class:muted", " chiave  "), ("", f"{inst.key_path or '—'}\n"),
            ("class:muted", " gruppo  "),
            (_GROUP_STYLES.get(inst.group, ""), f"{icon} {inst.group}\n"),
            ("class:muted", " tag     "), ("", f"{' '.join(inst.tags[:6]) or '—'}\n"),
            ("class:muted", " ultimo  "), ("", f"{self.recency.get(name, '—')}\n"),
            ("class:muted", " stato   "), (state_style, f"{state_text}\n\n"),
            ("class:muted", " $ "), ("", format_ssh_command(inst)),
        ]

    def header_fragments(self) -> list:
        shown = len(self.matches())
        return [
            ("class:header", " 🔐 ssh-conn"),
            ("class:muted", f"   {shown}/{len(self.instances)} istanze"),
        ]

    def keybar_fragments(self) -> list:
        if self.state["message"]:
            return [("class:message", f" {self.state['message']}")]
        keys = (
            ("⏎", "connetti"), ("^E", "modifica"), ("^D", "elimina"),
            ("^N", "nuova"), ("^T", "health"), ("^Y", "copia"),
            ("F1", "aiuto"), ("F2", "menu"), ("Esc", "esci"),
        )
        fragments: list = []
        for key, label in keys:
            fragments.append(("class:label", f" {key}"))
            fragments.append(("class:muted", f" {label} "))
        return fragments

    def help_fragments(self) -> list:
        fragments: list = []
        for key, description in _HELP_KEYS:
            fragments.append(("class:label", f" {key:<7}"))
            fragments.append(("", f"{description}\n"))
        return fragments

    # ------------------------------------------------------------- keys --

    def key_bindings(self) -> KeyBindings:
        kb = KeyBindings()

        def exit_with_selected(event, action: str) -> None:
            name = self.selected_name()
            if name:
                event.app.exit(result=(action, name))
            else:
                self.state["message"] = "Nessuna istanza selezionata."

        def move(delta: int) -> None:
            self.state["selected"] = int(self.state["selected"]) + delta

        @kb.add("up")
        def _(event) -> None:
            move(-1)

        @kb.add("down")
        def _(event) -> None:
            move(1)

        @kb.add("pageup")
        def _(event) -> None:
            move(-self.visible_rows())

        @kb.add("pagedown")
        def _(event) -> None:
            move(self.visible_rows())

        @kb.add("enter")
        def _(event) -> None:
            exit_with_selected(event, "connect")

        @kb.add("c-e")
        def _(event) -> None:
            exit_with_selected(event, "edit")

        @kb.add("c-d")
        def _(event) -> None:
            exit_with_selected(event, "delete")

        @kb.add("c-n")
        def _(event) -> None:
            event.app.exit(result=("new", None))

        @kb.add("f3")
        def _(event) -> None:
            event.app.exit(result=("import", None))

        @kb.add("f2")
        def _(event) -> None:
            event.app.exit(result=("menu", None))

        @kb.add("c-t")
        def _(event) -> None:
            self.health.clear()
            self.state["message"] = _HEALTH_RUNNING_MESSAGE
            event.app.create_background_task(self._health_task(event.app))

        @kb.add("c-y")
        def _(event) -> None:
            name = self.selected_name()
            if not name:
                self.state["message"] = "Nessuna istanza selezionata."
                return
            copied = _copy_to_clipboard(format_ssh_command(self.instances[name]))
            self.state["message"] = (
                "📋 Comando ssh copiato negli appunti."
                if copied
                else "Nessuno strumento clipboard disponibile (pbcopy/xclip/xsel)."
            )

        @kb.add("c-o")
        def _(event) -> None:
            self.state["preview"] = not self.state["preview"]

        @kb.add("f1")
        def _(event) -> None:
            self.state["help"] = not self.state["help"]

        @kb.add("escape", eager=True)
        def _(event) -> None:
            if self.state["help"]:
                self.state["help"] = False
                return
            if self.buffer.text:
                self.buffer.text = ""
                self.state["selected"] = 0
                return
            event.app.exit(result=("quit", None))

        @kb.add("c-c")
        @kb.add("c-g")
        def _(event) -> None:
            event.app.exit(result=("quit", None))

        return kb

    # ------------------------------------------------------------ build --

    def build_app(self) -> Application:
        list_window = Window(
            FormattedTextControl(self.list_fragments), wrap_lines=False
        )
        preview = ConditionalContainer(
            Frame(
                Window(
                    FormattedTextControl(self.preview_fragments),
                    wrap_lines=False,
                    width=Dimension(preferred=46, max=52),
                ),
                title="dettagli",
            ),
            filter=Condition(
                lambda: bool(self.state["preview"])
                and get_app().output.get_size().columns >= _PREVIEW_MIN_COLS
            ),
        )
        input_window = Window(BufferControl(buffer=self.buffer), height=1)
        search = VSplit(
            [
                Window(
                    FormattedTextControl(lambda: [("class:label", " Cerca › ")]),
                    height=1,
                    dont_extend_width=True,
                ),
                input_window,
            ]
        )
        root = HSplit(
            [
                Window(FormattedTextControl(self.header_fragments), height=1),
                search,
                VSplit([list_window, preview], padding=1),
                Window(FormattedTextControl(self.keybar_fragments), height=1),
            ]
        )
        help_float = Float(
            content=ConditionalContainer(
                Frame(
                    Window(
                        FormattedTextControl(self.help_fragments),
                        wrap_lines=False,
                        width=Dimension(preferred=52),
                        height=Dimension(preferred=len(_HELP_KEYS)),
                    ),
                    title="aiuto",
                ),
                filter=Condition(lambda: bool(self.state["help"])),
            )
        )
        layout = Layout(
            FloatContainer(content=root, floats=[help_float]),
            focused_element=input_window,
        )
        return Application(
            layout=layout,
            key_bindings=self.key_bindings(),
            style=_build_style(),
            full_screen=True,
            mouse_support=False,
        )


def run(
    instances: dict[str, SSHInstance],
    health_state: dict[str, health_mod.Status],
    start_query: str = "",
) -> tuple[str, str | None]:
    """Show the dashboard; return the (action, payload) chosen by the user."""
    dash = _Dashboard(instances, health_state, start_query=start_query)
    app = dash.build_app()

    def pre_run() -> None:
        app.create_background_task(dash._health_task(app))

    try:
        result = app.run(pre_run=pre_run)
    except (KeyboardInterrupt, EOFError):
        return ("quit", None)
    return result or ("quit", None)
