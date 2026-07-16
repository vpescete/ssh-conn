"""Terminal background detection (dark/light) and theme-aware colour palettes.

Detection order (first hit wins):
1. ``SSH_CONN_THEME`` env / explicit override via ``set_theme`` ("dark"|"light")
2. ``COLORFGBG`` env (set by several terminals)
3. OSC 11 query to the terminal (background colour) + luminance
4. fallback: "dark"
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass

_LUMINANCE_MIDPOINT = 127.0  # 0..255; above → light background


@dataclass(frozen=True)
class Palette:
    mode: str
    text: str
    muted: str  # readable secondary text (replaces the low-contrast "dim")
    accent: str
    recent: str
    health_ok: str
    health_bad: str
    health_timeout: str
    group_colors: dict[str, str]


_DARK = Palette(
    mode="dark",
    text="white",
    muted="grey70",
    accent="cyan",
    recent="magenta",
    health_ok="green",
    health_bad="red",
    health_timeout="yellow",
    group_colors={
        "OVH": "green",
        "GCP": "blue",
        "CL": "cyan",
        "OVS": "magenta",
        "Odoo": "yellow",
        "Buyprotect": "red",
        "other": "white",
    },
)

# Darker, higher-contrast variants that stay legible on a light background.
_LIGHT = Palette(
    mode="light",
    text="black",
    muted="grey37",
    accent="dark_cyan",
    recent="magenta3",
    health_ok="green4",
    health_bad="red3",
    health_timeout="dark_goldenrod",
    group_colors={
        "OVH": "green4",
        "GCP": "blue3",
        "CL": "dark_cyan",
        "OVS": "purple",
        "Odoo": "dark_goldenrod",
        "Buyprotect": "red3",
        "other": "black",
    },
)

_PALETTES: dict[str, Palette] = {"dark": _DARK, "light": _LIGHT}

_override: str | None = None
_cached_mode: str | None = None


def set_theme(value: str | None) -> None:
    """Force 'dark'/'light'; None or 'auto' re-enables auto-detection."""
    global _override, _cached_mode
    _override = value if value in ("dark", "light") else None
    _cached_mode = None


def active_mode() -> str:
    """Return the active theme ('dark' or 'light'), detecting once and caching."""
    global _cached_mode
    if _override is not None:
        return _override
    if _cached_mode is None:
        _cached_mode = _detect_mode()
    return _cached_mode


def active_palette() -> Palette:
    return _PALETTES[active_mode()]


def _detect_mode() -> str:
    env = os.environ.get("SSH_CONN_THEME", "").strip().lower()
    if env in ("dark", "light"):
        return env

    from_fgbg = _mode_from_colorfgbg(os.environ.get("COLORFGBG"))
    if from_fgbg is not None:
        return from_fgbg

    rgb = _query_osc11_background()
    if rgb is not None:
        r, g, b = rgb
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return "light" if luminance > _LUMINANCE_MIDPOINT else "dark"

    return "dark"


def _mode_from_colorfgbg(value: str | None) -> str | None:
    """Interpret COLORFGBG ('fg;bg' or 'fg;default;bg') by the background index."""
    if not value:
        return None
    try:
        bg = int(value.split(";")[-1])
    except ValueError:
        return None
    # xterm palette: 0-6 and 8 are dark; 7 and 9-15 are light.
    return "light" if bg == 7 or bg >= 9 else "dark"


def _query_osc11_background(timeout: float = 0.2) -> tuple[int, int, int] | None:
    """Ask the terminal for its background colour via OSC 11. None if unavailable."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return None
    try:
        import select
        import termios
        import tty
    except ImportError:  # non-POSIX terminal
        return None

    fd = sys.stdin.fileno()
    try:
        original = termios.tcgetattr(fd)
    except termios.error:
        return None

    response = ""
    try:
        tty.setraw(fd)
        sys.stdout.write("\x1b]11;?\x07")
        sys.stdout.flush()
        while True:
            ready, _, _ = select.select([fd], [], [], timeout)
            if not ready:
                break
            chunk = os.read(fd, 32).decode("latin-1", "ignore")
            if not chunk:
                break
            response += chunk
            if "\x07" in response or "\x1b\\" in response:
                break
    except Exception:  # noqa: BLE001 — detection is best-effort, never fatal
        return None
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, original)
        except termios.error:
            pass

    return _parse_osc11(response)


def _parse_osc11(response: str) -> tuple[int, int, int] | None:
    match = re.search(r"rgb:([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)", response)
    if not match:
        return None

    def to_byte(component: str) -> int:
        value = int(component, 16)
        scale = 16 ** len(component) - 1
        return round(value / scale * 255)

    return to_byte(match.group(1)), to_byte(match.group(2)), to_byte(match.group(3))
