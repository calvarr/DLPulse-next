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


def _is_dotnet_root(path: Path) -> bool:
    """CoreCLR host + desktop shared framework (pythonnet / WinForms)."""
    if not (path / "host" / "fxr").is_dir():
        return False
    desktop = path / "shared" / "Microsoft.WindowsDesktop.App"
    return desktop.is_dir() and any(desktop.iterdir())


def _dotnet_root_candidates() -> list[Path]:
    out: list[Path] = []
    base = install_dir()
    if base is not None:
        for rel in ("dotnet", "runtime/dotnet", "_internal/dotnet"):
            out.append((base / rel).resolve())
    for env_key in ("DOTNET_ROOT", "PYTHONNET_CORECLR_DOTNET_ROOT"):
        raw = (os.environ.get(env_key) or "").strip()
        if raw:
            out.append(Path(raw).expanduser().resolve())
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    out.append(Path(pf).expanduser() / "dotnet")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    out.append(Path(pf86).expanduser() / "dotnet")
    seen: set[str] = set()
    unique: list[Path] = []
    for p in out:
        key = str(p)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def find_bundled_dotnet_root() -> Path | None:
    """Portable dotnet next to the app, else system-wide .NET Desktop install."""
    for candidate in _dotnet_root_candidates():
        if _is_dotnet_root(candidate):
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
        base / "_internal" / "WebView2Runtime",
    )
    for root in roots:
        if not root.is_dir():
            continue
        for exe in root.rglob("msedgewebview2.exe"):
            return exe.parent.resolve()
        for exe in root.rglob("msedge.exe"):
            return exe.parent.resolve()
    return None


def apply_bundled_windows_runtimes() -> None:
    """Point CoreCLR and pywebview at runtimes copied by the NSIS installer."""
    if sys.platform != "win32":
        return

    dotnet = find_bundled_dotnet_root()
    if dotnet is not None:
        root_s = str(dotnet)
        os.environ["DOTNET_ROOT"] = root_s
        os.environ["PYTHONNET_CORECLR_DOTNET_ROOT"] = root_s
        os.environ["PATH"] = root_s + os.pathsep + os.environ.get("PATH", "")
        _log.info("DOTNET_ROOT=%s", dotnet)

    wv2 = find_bundled_webview2_folder()
    if wv2 is not None:
        os.environ["DLPULSE_WEBVIEW2_RUNTIME"] = str(wv2)
        try:
            import webview

            webview.settings["WEBVIEW2_RUNTIME_PATH"] = str(wv2)
            _log.info("Bundled WEBVIEW2_RUNTIME_PATH=%s", wv2)
        except Exception as ex:
            _log.warning("Could not set pywebview WEBVIEW2_RUNTIME_PATH: %s", ex)
