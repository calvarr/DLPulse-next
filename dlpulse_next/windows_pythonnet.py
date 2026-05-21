"""Configure and verify pythonnet (CoreCLR) before pywebview on Windows."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_log = logging.getLogger(__name__)

_bootstrapped = False


def _bundle_roots() -> list[Path]:
    roots: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(Path(meipass))
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        roots.append(exe_dir)
        internal = exe_dir / "_internal"
        if internal.is_dir():
            roots.append(internal)
    return roots


def _runtimeconfig_candidates() -> list[Path]:
    out: list[Path] = []
    for root in _bundle_roots():
        out.extend(
            [
                root / "windows_runtimeconfig.json",
                root / "packaging" / "pyinstaller" / "windows_runtimeconfig.json",
            ]
        )
    repo = Path(__file__).resolve().parents[1]
    out.append(repo / "packaging" / "pyinstaller" / "windows_runtimeconfig.json")
    seen: set[str] = set()
    unique: list[Path] = []
    for p in out:
        key = str(p)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _find_python_runtime_dll() -> Path | None:
    names = ("Python.Runtime.dll",)
    subdirs = (
        "pythonnet/runtime",
        "runtime",
        "pythonnet",
        ".",
    )
    for root in _bundle_roots():
        for sub in subdirs:
            for name in names:
                p = (root / sub / name).resolve()
                if p.is_file():
                    return p
    return None


def _apply_path_for_native_dlls() -> None:
    parts: list[str] = []
    for root in _bundle_roots():
        s = str(root)
        if s not in parts:
            parts.append(s)
    existing = os.environ.get("PATH", "")
    for p in existing.split(os.pathsep):
        if p and p not in parts:
            parts.append(p)
    os.environ["PATH"] = os.pathsep.join(parts)


def configure_windows_pythonnet() -> Path | None:
    """Set env vars for CoreCLR. Call before ``import clr`` or ``import webview``."""
    if sys.platform != "win32":
        return None

    _apply_path_for_native_dlls()
    os.environ.setdefault("PYTHONNET_RUNTIME", "coreclr")

    rt_dll = _find_python_runtime_dll()
    if rt_dll is not None:
        os.environ["PYTHONNET_PYDLL"] = str(rt_dll)
        _log.info("PYTHONNET_PYDLL=%s", rt_dll)

    cfg_path: Path | None = None
    for cfg in _runtimeconfig_candidates():
        if cfg.is_file():
            cfg_path = cfg.resolve()
            os.environ["PYTHONNET_CORECLR_RUNTIME_CONFIG"] = str(cfg_path)
            _log.info("PYTHONNET_CORECLR_RUNTIME_CONFIG=%s", cfg_path)
            break

    return cfg_path


def bootstrap_pythonnet() -> None:
    """Load CoreCLR runtime (pythonnet 3). Safe to call multiple times."""
    global _bootstrapped
    if _bootstrapped or sys.platform != "win32":
        return

    cfg_path = configure_windows_pythonnet()
    try:
        from pythonnet import load

        if cfg_path is not None:
            load("coreclr", runtime_config=str(cfg_path))
        else:
            load("coreclr")
        _log.info("pythonnet.load(coreclr) OK")
    except Exception as ex:
        _log.warning("pythonnet.load failed (%s); relying on env vars", ex)

    _bootstrapped = True


def ensure_pythonnet_ready() -> None:
    """
    Verify pythonnet + WinForms load (pywebview on Windows needs both).
    Raises RuntimeError with a helpful message on failure.
    """
    if sys.platform != "win32":
        return

    bootstrap_pythonnet()

    try:
        import clr  # noqa: F401
    except Exception as ex:
        raise RuntimeError(
            "pythonnet/clr could not be loaded in this build. "
            "Install Microsoft .NET Desktop Runtime 6+ and WebView2, then reinstall DLPulse Next. "
            f"Technical detail: {ex}"
        ) from ex

    try:
        import clr as _clr

        _clr.AddReference("System.Windows.Forms")
    except Exception as ex:
        raise RuntimeError(
            "pythonnet loaded but System.Windows.Forms is unavailable. "
            "Install Microsoft .NET Desktop Runtime 6 or newer (Windows Desktop), then retry. "
            f"Technical detail: {ex}"
        ) from ex
