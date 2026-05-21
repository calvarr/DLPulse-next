"""Configure pythonnet (CoreCLR + Windows Desktop) before pywebview on Windows."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _runtimeconfig_candidates() -> list[Path]:
    out: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        root = Path(meipass)
        out.extend(
            [
                root / "windows_runtimeconfig.json",
                root / "packaging" / "pyinstaller" / "windows_runtimeconfig.json",
            ]
        )
    here = Path(__file__).resolve().parent
    repo = here.parent
    out.append(repo / "packaging" / "pyinstaller" / "windows_runtimeconfig.json")
    return out


def configure_windows_pythonnet() -> Path | None:
    """Must run before ``import clr`` or ``import webview`` on Windows."""
    if sys.platform != "win32":
        return None
    os.environ.setdefault("PYTHONNET_RUNTIME", "coreclr")
    for cfg in _runtimeconfig_candidates():
        if cfg.is_file():
            os.environ["PYTHONNET_CORECLR_RUNTIME_CONFIG"] = str(cfg.resolve())
            return cfg.resolve()
    return None
