"""Design system "Giấy & Mực" for the desktop app (same tokens as apps/web/src/index.css).

Every colour is a (light, dark) pair that CustomTkinter switches automatically. Rules for new screens
are in docs/conventions/design.md: use these tokens only, never raw colours inside widgets.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import customtkinter as ctk

Pair = tuple[str, str]  # (light, dark)

BG: Pair = ("#f5f1ea", "#14120f")
SURFACE: Pair = ("#fffdf8", "#1c1916")
SURFACE_2: Pair = ("#f0ebe1", "#25211d")
SURFACE_3: Pair = ("#e7e0d3", "#2f2a25")
BORDER: Pair = ("#e2dacb", "#34302a")
BORDER_STRONG: Pair = ("#cfc5b2", "#4a443c")
TEXT: Pair = ("#26221c", "#f1ece3")
TEXT_2: Pair = ("#51493d", "#c9c1b4")
MUTED: Pair = ("#7b7264", "#928a7c")
ACCENT: Pair = ("#a95a05", "#f0a93e")
ACCENT_HOVER: Pair = ("#8f4b03", "#f7bb5c")
ACCENT_INK: Pair = ("#ffffff", "#241600")  # text on an accent background
ACCENT_SOFT: Pair = ("#f6ede0", "#392d1c")  # current-sentence highlight
SUCCESS: Pair = ("#1f7a4a", "#6fcf97")
WARNING: Pair = ("#8a6200", "#f2c94c")
DANGER: Pair = ("#c0392b", "#ef6a5b")
CHARTS: tuple[Pair, ...] = (
    ("#c27a12", "#f0a93e"), ("#2e8b57", "#6fcf97"), ("#2f6fb5", "#6aa9e9"),
    ("#7a4fb8", "#b48ae6"), ("#c0392b", "#ef6a5b"), ("#1f8a8a", "#4fc3c3"),
)

# Keyword sets for buttons that are not the default (accent) button.
SECONDARY: dict[str, Any] = {"fg_color": SURFACE_3, "hover_color": BORDER_STRONG, "text_color": TEXT}
GHOST: dict[str, Any] = {"fg_color": "transparent", "hover_color": SURFACE_3, "text_color": TEXT_2}
ACCENT_SOFT_BUTTON: dict[str, Any] = {"fg_color": ACCENT_SOFT, "hover_color": SURFACE_3, "text_color": ACCENT}
DANGER_BUTTON: dict[str, Any] = {"fg_color": DANGER, "hover_color": ("#9e2d22", "#d9534a"), "text_color": ("#ffffff", "#ffffff")}

APPEARANCES = ("System", "Light", "Dark")
APPEARANCE_LABEL = {"System": "Tự động", "Light": "Sáng", "Dark": "Tối"}

_UI_FONTS = ("Be Vietnam Pro", "Inter", "Segoe UI", "Noto Sans", "DejaVu Sans")
_READ_FONTS = ("Source Serif 4", "Literata", "Georgia", "Noto Serif", "DejaVu Serif", "Times New Roman")
ui_family = "TkDefaultFont"
read_family = "TkTextFont"


def mode_color(pair: Pair) -> str:
    """The colour of `pair` for the current appearance (for widgets that cannot take a pair, e.g. Tk tags)."""
    return pair[1] if ctk.get_appearance_mode() == "Dark" else pair[0]


def _settings_file() -> Path:
    base = os.getenv("AUDIOBOOK_TTS_CONFIG_DIR")
    return (Path(base) if base else Path.home() / ".config" / "audiobook-tts") / "desktop.json"


def _first_installed(candidates: tuple[str, ...], fallback: str) -> str:
    try:
        from tkinter import font as tkfont

        installed = set(tkfont.families())
    except (ImportError, RuntimeError, AttributeError):  # no Tk (tests) or no root window yet
        return fallback
    return next((name for name in candidates if name in installed), fallback)


def font(size: int = 13, weight: str = "normal", serif: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(family=read_family if serif else ui_family, size=size, weight=weight)  # type: ignore[arg-type]


def apply() -> None:
    """Patch the CustomTkinter theme with our tokens. Call once, after the Tk root exists, before any widget."""
    global ui_family, read_family
    ctk.set_default_color_theme("blue")
    ui_family = _first_installed(_UI_FONTS, "TkDefaultFont")
    read_family = _first_installed(_READ_FONTS, "TkTextFont")

    t = ctk.ThemeManager.theme
    t["CTkFont"]["family"] = ui_family  # already reduced to the current platform when the theme is loaded
    t["CTk"]["fg_color"] = BG
    t["CTkToplevel"]["fg_color"] = BG
    t["CTkFrame"].update(corner_radius=12, fg_color=SURFACE, top_fg_color=SURFACE_2, border_color=BORDER)
    t["CTkButton"].update(corner_radius=10, fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=ACCENT_INK,
                          text_color_disabled=MUTED)
    t["CTkLabel"].update(text_color=TEXT)
    t["CTkEntry"].update(corner_radius=10, border_width=1, fg_color=SURFACE_2, border_color=BORDER_STRONG,
                         text_color=TEXT, placeholder_text_color=MUTED)
    t["CTkCheckBox"].update(fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color=BORDER_STRONG,
                            checkmark_color=ACCENT_INK, text_color=TEXT)
    t["CTkRadioButton"].update(fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color=BORDER_STRONG, text_color=TEXT)
    t["CTkSwitch"].update(progress_color=ACCENT, fg_color=SURFACE_3, button_color=TEXT_2, button_hover_color=TEXT)
    t["CTkProgressBar"].update(fg_color=SURFACE_3, progress_color=ACCENT)
    t["CTkSlider"].update(fg_color=SURFACE_3, progress_color=ACCENT, button_color=ACCENT, button_hover_color=ACCENT_HOVER)
    t["CTkOptionMenu"].update(corner_radius=10, fg_color=SURFACE_2, button_color=SURFACE_3,
                              button_hover_color=BORDER_STRONG, text_color=TEXT)
    t["CTkComboBox"].update(corner_radius=10, border_width=1, fg_color=SURFACE_2, border_color=BORDER_STRONG,
                            button_color=SURFACE_3, button_hover_color=BORDER_STRONG, text_color=TEXT)
    t["CTkScrollbar"].update(button_color=BORDER_STRONG, button_hover_color=MUTED)
    t["CTkSegmentedButton"].update(corner_radius=999, border_width=3, fg_color=SURFACE_2,
                                   selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
                                   unselected_color=SURFACE_2, unselected_hover_color=SURFACE_3,
                                   text_color=TEXT, text_color_disabled=MUTED)
    t["CTkTextbox"].update(corner_radius=14, fg_color=SURFACE, border_color=BORDER, border_width=1, text_color=TEXT,
                           scrollbar_button_color=BORDER_STRONG, scrollbar_button_hover_color=MUTED)
    t["CTkScrollableFrame"].update(label_fg_color=SURFACE_2)
    t["DropdownMenu"].update(fg_color=SURFACE_2, hover_color=SURFACE_3, text_color=TEXT)


# ---------------------------------------------------------------------------- saved appearance

def load_appearance() -> str:
    try:
        value = json.loads(_settings_file().read_text(encoding="utf-8")).get("appearance")
    except (OSError, ValueError, AttributeError):
        return "System"
    return value if value in APPEARANCES else "System"


def save_appearance(value: str) -> None:
    try:
        _settings_file().parent.mkdir(parents=True, exist_ok=True)
        _settings_file().write_text(json.dumps({"appearance": value}), encoding="utf-8")
    except OSError:
        pass  # the choice just is not remembered
