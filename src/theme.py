"""Centralised visual constants — colors, fonts, sizes.

All views should import from here instead of hard-coding hex values
so that the UI remains visually coherent.
"""

import sys


# ── Color palette (semantic) ────────────────────────────────────────

# Primary brand colour (indigo) — main CTA buttons, accents
PRIMARY = "#6366f1"
PRIMARY_HOVER = "#4f46e5"
PRIMARY_DEEP = "#4338ca"

# Status colors
SUCCESS = "#22c55e"
SUCCESS_HOVER = "#16a34a"
DANGER = "#ef4444"
DANGER_HOVER = "#dc2626"
WARNING = "#eab308"
WARNING_HOVER = "#ca8a04"
INFO = "#06b6d4"
INFO_HOVER = "#0891b2"
ACCENT = "#f97316"          # orange — capture / HOME-ish actions
ACCENT_HOVER = "#ea580c"

# Neutrals
NEUTRAL = "#4b5563"
NEUTRAL_HOVER = "#374151"
NEUTRAL_SOFT = "#6b7280"
NEUTRAL_SOFT_HOVER = "#4b5563"

# Surfaces / backgrounds
SURFACE_DARK = "#0f0f1a"     # canvas / textbox background
SURFACE_MID = "#1a1a2e"      # scrollable frame inner bg
SURFACE_HEADER = "#1e1b4b"   # top app header / editor toolbar
SURFACE_CARD = "#1f2937"     # section card subtle
SLATE = "#334155"
SLATE_HOVER = "#475569"

# Text colors
TEXT_PRIMARY = "#ffffff"
TEXT_MUTED = "#9ca3af"
TEXT_SUBTLE = "#6b7280"
TEXT_ON_DARK = "#cbd5e1"

# Selection / drag highlight
SELECT_BG = "#4f46e5"
DRAG_BG = "#334155"
DRAG_BORDER = "#6366f1"
DONE_BG = "#15803d"
RUNNING_BG = "#0e7490"

# Buttons by semantic group (for macro quick-builder etc.)
TOKEN_FACE = "#2563eb"       # A B X Y
TOKEN_FACE_HOVER = "#1d4ed8"
TOKEN_DPAD = "#0891b2"       # DUP DDOWN DLEFT DRIGHT
TOKEN_DPAD_HOVER = "#0e7490"
TOKEN_SHOULDER = PRIMARY_DEEP   # L R ZL ZR LSTICK RSTICK
TOKEN_SHOULDER_HOVER = "#3730a3"
TOKEN_SYSTEM = NEUTRAL       # HOME CAPTURE PLUS MINUS
TOKEN_SYSTEM_HOVER = NEUTRAL_HOVER
TOKEN_WAIT = "#854d0e"       # Wxxx
TOKEN_WAIT_HOVER = "#713f12"


# ── Button height tiers ─────────────────────────────────────────────

BTN_H_SM = 26
BTN_H_MD = 32
BTN_H_LG = 40

CORNER_SM = 6
CORNER_MD = 8
CORNER_LG = 12

# ── Section / spacing ───────────────────────────────────────────────

SECTION_PADX = 16
SECTION_PADY = 8
SECTION_INNER_PADX = 16
SECTION_INNER_PADY_TOP = (12, 8)
SECTION_INNER_PADY_BOTTOM = (4, 12)
ROW_PADY = 6


# ── Fonts (cross-platform) ──────────────────────────────────────────

def _mono_family() -> str:
    """Return the best available monospace family for the current OS."""
    if sys.platform == "darwin":
        return "Menlo"
    if sys.platform.startswith("win"):
        return "Consolas"
    return "DejaVu Sans Mono"


MONO_FAMILY = _mono_family()
UI_FAMILY = ""  # let customtkinter pick the system UI font

FONT_TITLE = (UI_FAMILY, 18, "bold")
FONT_SECTION = (UI_FAMILY, 16, "bold")
FONT_SUBSECTION = (UI_FAMILY, 14, "bold")
FONT_BODY = (UI_FAMILY, 12)
FONT_BODY_BOLD = (UI_FAMILY, 12, "bold")
FONT_HINT = (UI_FAMILY, 11)
FONT_SMALL = (UI_FAMILY, 10)

FONT_MONO = (MONO_FAMILY, 12)
FONT_MONO_SM = (MONO_FAMILY, 11)
FONT_MONO_XS = (MONO_FAMILY, 10)
FONT_MONO_BOLD = (MONO_FAMILY, 11, "bold")


# ── Helpers ─────────────────────────────────────────────────────────

def darken(hex_color: str, factor: float = 0.8) -> str:
    """Return a slightly darker hex colour."""
    c = hex_color.lstrip("#")
    r, g, b = int(c[:2], 16), int(c[2:4], 16), int(c[4:], 16)
    return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"
