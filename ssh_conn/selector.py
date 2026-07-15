"""Interactive fuzzy picker (fzf-style) built on prompt_toolkit.

Provides an arrow-navigable, incrementally-filtered list. Falls back
gracefully: callers should check `is_available()` and use a plain text
prompt when there is no TTY.
"""
from __future__ import annotations

import sys

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.styles import Style

MAX_VISIBLE = 15

_STYLE = Style.from_dict(
    {
        "selected": "reverse",
        "item": "",
        "nomatch": "ansiyellow",
        "label": "ansicyan bold",
        "counter": "ansimagenta",
        "hint": "ansibrightblack",
    }
)


def is_available() -> bool:
    """True when an interactive full-screen picker can be shown."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _subsequence_score(query: str, text: str) -> tuple[int, int] | None:
    """Return a sort key if `query` is a subsequence of `text`, else None.

    Lower is better: prefers tighter spans and earlier first matches.
    """
    pos = 0
    first: int | None = None
    last = 0
    for ch in query:
        idx = text.find(ch, pos)
        if idx == -1:
            return None
        if first is None:
            first = idx
        last = idx
        pos = idx + 1
    return (last - (first or 0), first or 0)


def filter_names(names: list[str], query: str) -> list[str]:
    """Return `names` matching `query` as a fuzzy subsequence, best-ranked first."""
    query = query.strip().lower()
    if not query:
        return list(names)
    scored = []
    for name in names:
        score = _subsequence_score(query, name.lower())
        if score is not None:
            scored.append((score, name.lower(), name))
    scored.sort()
    return [name for _, _, name in scored]


def window_start(count: int, selected: int, max_visible: int = MAX_VISIBLE) -> int:
    """First index of the visible slice keeping `selected` roughly centred."""
    if count <= max_visible:
        return 0
    return max(0, min(selected - max_visible // 2, count - max_visible))


def fuzzy_select(names: list[str], prompt_label: str = "Seleziona") -> str | None:
    """Show an interactive picker; return the chosen name or None if cancelled."""
    if not names:
        return None

    buffer = Buffer(multiline=False)
    state: dict[str, object] = {"selected": 0, "matches": list(names)}

    def compute_matches() -> list[str]:
        matches = filter_names(names, buffer.text)
        state["matches"] = matches
        selected = int(state["selected"])
        state["selected"] = min(max(selected, 0), max(0, len(matches) - 1))
        return matches

    def list_fragments():
        matches = compute_matches()
        if not matches:
            return [("class:nomatch", "  (nessun risultato)\n")]
        selected = int(state["selected"])
        start = window_start(len(matches), selected)
        visible = matches[start : start + MAX_VISIBLE]
        fragments = []
        for i, name in enumerate(visible, start=start):
            style = "class:selected" if i == selected else "class:item"
            marker = "›" if i == selected else " "
            fragments.append((style, f"{marker} {name}\n"))
        return fragments

    def counter_fragments():
        matches = compute_matches()
        return [("class:counter", f" {len(matches)}/{len(names)} risultati")]

    def label_fragments():
        return [("class:label", f"{prompt_label} › ")]

    kb = KeyBindings()

    @kb.add("up")
    @kb.add("c-p")
    def _(event):
        state["selected"] = int(state["selected"]) - 1

    @kb.add("down")
    @kb.add("c-n")
    def _(event):
        state["selected"] = int(state["selected"]) + 1

    @kb.add("enter")
    def _(event):
        matches = compute_matches()
        if matches:
            event.app.exit(result=matches[int(state["selected"])])
        else:
            event.app.exit(result=None)

    @kb.add("c-c")
    @kb.add("c-g")
    def _(event):
        event.app.exit(result=None)

    list_window = Window(
        content=FormattedTextControl(list_fragments),
        height=Dimension(min=1, preferred=MAX_VISIBLE, max=MAX_VISIBLE),
        wrap_lines=False,
    )
    hint_window = Window(
        content=FormattedTextControl(
            lambda: [("class:hint", " ↑↓ naviga · digita per filtrare · Invio conferma · Ctrl-C annulla")]
        ),
        height=1,
    )
    counter_window = Window(FormattedTextControl(counter_fragments), height=1)
    label_window = Window(
        FormattedTextControl(label_fragments), height=1, dont_extend_width=True
    )
    input_window = Window(BufferControl(buffer=buffer), height=1)

    root = HSplit(
        [
            counter_window,
            list_window,
            hint_window,
            VSplit([label_window, input_window]),
        ]
    )
    layout = Layout(root, focused_element=input_window)

    app: Application = Application(
        layout=layout,
        key_bindings=kb,
        style=_STYLE,
        full_screen=True,
        mouse_support=False,
    )
    try:
        return app.run()
    except (KeyboardInterrupt, EOFError):
        return None


def menu_select(
    options: list[tuple[str, str]],
    title: str | None = None,
    subtitle: str | None = None,
) -> str | None:
    """Arrow-navigable menu over (key, label) options.

    Returns the selected key, or None if cancelled. The option key can also be
    pressed directly as a hotkey to select it without moving the cursor.
    """
    if not options:
        return None

    state: dict[str, int] = {"selected": 0}

    def menu_fragments():
        fragments = []
        for i, (key, label) in enumerate(options):
            selected = i == state["selected"]
            style = "class:selected" if selected else "class:item"
            marker = "›" if selected else " "
            fragments.append((style, f"{marker} {key}. {label}\n"))
        return fragments

    kb = KeyBindings()

    @kb.add("up")
    @kb.add("c-p")
    def _(event):
        state["selected"] = (state["selected"] - 1) % len(options)

    @kb.add("down")
    @kb.add("c-n")
    def _(event):
        state["selected"] = (state["selected"] + 1) % len(options)

    @kb.add("enter")
    def _(event):
        event.app.exit(result=options[state["selected"]][0])

    @kb.add("c-c")
    @kb.add("c-g")
    def _(event):
        event.app.exit(result=None)

    for key, _label in options:
        @kb.add(key)
        def _(event, key=key):
            event.app.exit(result=key)

    children = []
    if title:
        children.append(
            Window(FormattedTextControl(lambda: [("class:label", title)]), height=1)
        )
    if subtitle:
        children.append(
            Window(FormattedTextControl(lambda: [("class:hint", subtitle)]), height=1)
        )
    menu_window = Window(
        FormattedTextControl(menu_fragments, focusable=True, show_cursor=False),
        height=Dimension(min=1, preferred=len(options)),
    )
    children.append(menu_window)
    children.append(
        Window(
            FormattedTextControl(
                lambda: [("class:hint", " ↑↓ naviga · Invio conferma · o premi il tasto")]
            ),
            height=1,
        )
    )

    layout = Layout(HSplit(children), focused_element=menu_window)
    app: Application = Application(
        layout=layout,
        key_bindings=kb,
        style=_STYLE,
        full_screen=True,
        mouse_support=False,
    )
    try:
        return app.run()
    except (KeyboardInterrupt, EOFError):
        return None
