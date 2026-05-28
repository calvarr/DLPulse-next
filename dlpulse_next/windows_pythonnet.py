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
    try:
        from dlpulse_next.windows_bundled_runtimes import apply_bundled_windows_runtimes

        apply_bundled_windows_runtimes()
    except Exception:
        pass
    # Prefer .NET Framework on Windows for pywebview WinForms interop.
    # WebView2 WinForms bindings can fail under CoreCLR with missing legacy WinForms types.
    os.environ.setdefault("PYTHONNET_RUNTIME", "netfx")

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


def _bundled_dotnet_root() -> Path | None:
    try:
        from dlpulse_next.windows_bundled_runtimes import find_bundled_dotnet_root

        return find_bundled_dotnet_root()
    except Exception:
        return None


def bootstrap_pythonnet() -> None:
    """Load CoreCLR runtime (pythonnet 3). Safe to call multiple times."""
    global _bootstrapped
    if _bootstrapped or sys.platform != "win32":
        return

    cfg_path = configure_windows_pythonnet()
    dotnet_root = _bundled_dotnet_root()
    if dotnet_root is not None:
        root_s = str(dotnet_root)
        os.environ["DOTNET_ROOT"] = root_s
        os.environ["PYTHONNET_CORECLR_DOTNET_ROOT"] = root_s

    try:
        from pythonnet import load
    except Exception as ex:
        _log.warning("pythonnet import failed (%s); relying on env vars", ex)
        _bootstrapped = True
        return

    runtime_pref = (os.environ.get("PYTHONNET_RUNTIME") or "").strip().lower() or "netfx"
    if runtime_pref == "netfx":
        try:
            load("netfx")
            _log.info("pythonnet.load(netfx) OK")
            _bootstrapped = True
            return
        except Exception as ex:
            _log.warning("pythonnet.load(netfx) failed (%s); trying coreclr", ex)
            os.environ["PYTHONNET_RUNTIME"] = "coreclr"

    load_kw: dict[str, str] = {}
    if cfg_path is not None:
        load_kw["runtime_config"] = str(cfg_path)
    if dotnet_root is not None:
        load_kw["dotnet_root"] = str(dotnet_root)

    try:
        load("coreclr", **load_kw)
        _log.info("pythonnet.load(coreclr) OK dotnet_root=%s", dotnet_root)
    except Exception as ex:
        _log.warning("pythonnet.load(coreclr) failed (%s); relying on env vars", ex)

    _bootstrapped = True


def ensure_pythonnet_ready() -> None:
    """
    Verify pythonnet + WinForms load (pywebview on Windows needs both).
    Raises RuntimeError with a helpful message on failure.
    """
    if sys.platform != "win32":
        return

    bootstrap_pythonnet()

    dotnet_root = _bundled_dotnet_root()
    if dotnet_root is not None:
        root_s = str(dotnet_root)
        os.environ["DOTNET_ROOT"] = root_s
        os.environ["PYTHONNET_CORECLR_DOTNET_ROOT"] = root_s

    try:
        import clr  # noqa: F401
    except Exception as ex:
        if dotnet_root is not None:
            detail = str(ex)
        else:
            detail = (
                f"{ex} (.NET Desktop not found next to the app or under Program Files\\dotnet — "
                "reinstall the latest DLPulse Next installer as Administrator, or install "
                ".NET Desktop 8 x64 from Microsoft)"
            )
        raise RuntimeError(
            "pythonnet/clr could not be loaded. Reinstall DLPulse Next from the latest "
            f"GitHub release (bundled .NET Desktop). Technical detail: {detail}"
        ) from ex

    try:
        import clr as _clr

        _clr.AddReference("System.Windows.Forms")
        # pywebview/winforms imports `SystemEvents` from `Microsoft.Win32` at module import time.
        # Preload it on CoreCLR where assembly resolution can fail without an explicit reference.
        if (os.environ.get("PYTHONNET_RUNTIME") or "").strip().lower() == "coreclr":
            _clr.AddReference("Microsoft.Win32.SystemEvents")
    except Exception as ex:
        raise RuntimeError(
            "pythonnet loaded but required WinForms assemblies are unavailable. Reinstall the latest "
            f"DLPulse Next build (includes .NET Desktop). Technical detail: {ex}"
        ) from ex
