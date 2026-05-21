"""Use WebView2 and .NET Desktop runtimes shipped next to the Windows installer."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_log = logging.getLogger(__name__)


def install_dir() -> Path | None:
    if sys.platform != "win32":
        return None
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return None


def find_bundled_dotnet_root() -> Path | None:
    """Folder layout from ``windowsdesktop-runtime-*-win-x64.zip`` (contains host/, shared/)."""
    base = install_dir()
    if base is None:
        return None
    for candidate in (base / "dotnet", base / "runtime" / "dotnet"):
        if (candidate / "host").is_dir() and (candidate / "shared").is_dir():
            return candidate.resolve()
    return None


def find_bundled_webview2_folder() -> Path | None:
    """Directory passed to pywebview as ``WEBVIEW2_RUNTIME_PATH`` (contains msedgewebview2.exe)."""
    base = install_dir()
    if base is None:
        return None
    roots = (
        base / "WebView2Runtime",
        base / "runtime" / "WebView2Runtime",
    )
    for root in roots:
        if not root.is_dir():
            continue
        for exe in root.rglob("msedgewebview2.exe"):
            return exe.parent.resolve()
        # Some layouts nest version folders
        for exe in root.rglob("msedge.exe"):
            return exe.parent.resolve()
    return None


def apply_bundled_windows_runtimes() -> None:
    """Point CoreCLR and pywebview at runtimes copied by the NSIS installer."""
    if sys.platform != "win32":
        return

    dotnet = find_bundled_dotnet_root()
    if dotnet is not None:
        os.environ["DOTNET_ROOT"] = str(dotnet)
        os.environ["PATH"] = str(dotnet) + os.pathsep + os.environ.get("PATH", "")
        _log.info("Bundled DOTNET_ROOT=%s", dotnet)

    wv2 = find_bundled_webview2_folder()
    if wv2 is not None:
        os.environ["DLPULSE_WEBVIEW2_RUNTIME"] = str(wv2)
        try:
            import webview

            webview.settings["WEBVIEW2_RUNTIME_PATH"] = str(wv2)
            _log.info("Bundled WEBVIEW2_RUNTIME_PATH=%s", wv2)
        except Exception as ex:
            _log.warning("Could not set pywebview WEBVIEW2_RUNTIME_PATH: %s", ex)
