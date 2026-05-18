"""DLPulse icon paths (SVG in UI; PNG/ICO for native toolkits)."""
from __future__ import annotations

from pathlib import Path

_STATIC = Path(__file__).resolve().parent / "static"
ICON_SVG_DARK = _STATIC / "dlpulse_icon.svg"
ICON_SVG_LIGHT = _STATIC / "dlpulse_icon_light.svg"
ICON_SVG = ICON_SVG_DARK
ICON_PNG = _STATIC / "dlpulse_icon.png"
ICON_ICO = _STATIC / "dlpulse_icon.ico"
ICON_URL = "/static/dlpulse_icon.svg"
ICON_URL_LIGHT = "/static/dlpulse_icon_light.svg"


def window_icon_path() -> str | None:
    """File path for pywebview / GTK window icon (PNG)."""
    if ICON_PNG.is_file():
        return str(ICON_PNG)
    return None


def pyinstaller_icon_path() -> str | None:
    """File path for PyInstaller ``EXE(icon=…)`` on Windows."""
    if ICON_ICO.is_file():
        return str(ICON_ICO)
    if ICON_PNG.is_file():
        return str(ICON_PNG)
    return None
