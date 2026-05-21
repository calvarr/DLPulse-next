"""Frozen-app startup: crash logs and user-visible errors (Windows installer / PyInstaller)."""
from __future__ import annotations

import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def log_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or Path.home())
        return (base / "DLPulseNext" / "logs").resolve()
    return (Path.home() / ".local" / "state" / "dlpulse-next" / "logs").resolve()


def setup_packaged_logging() -> Path | None:
    """File logging when running as a packaged app (or when DLPULSE_DEBUG=1)."""
    if not is_frozen() and not os.environ.get("DLPULSE_DEBUG"):
        return None
    try:
        d = log_dir()
        d.mkdir(parents=True, exist_ok=True)
        log_file = d / "startup.log"
        logging.basicConfig(
            level=logging.DEBUG if os.environ.get("DLPULSE_DEBUG") else logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            handlers=[
                logging.FileHandler(log_file, encoding="utf-8"),
                logging.StreamHandler(sys.stderr) if os.environ.get("DLPULSE_DEBUG") else logging.NullHandler(),
            ],
            force=True,
        )
        logging.getLogger(__name__).info("DLPulse Next starting (frozen=%s)", is_frozen())
        return log_file
    except OSError:
        return None


def _append_crash_log(exc: BaseException) -> Path | None:
    try:
        d = log_dir()
        d.mkdir(parents=True, exist_ok=True)
        path = d / "crash.log"
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        block = f"\n--- {stamp} ---\n{traceback.format_exc()}\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(block)
        return path
    except OSError:
        return None


def show_fatal_error(title: str, message: str) -> None:
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR
            return
        except Exception:
            pass
    print(f"{title}\n{message}", file=sys.stderr, flush=True)


def report_fatal_error(exc: BaseException, *, context: str = "startup") -> None:
    log_path = _append_crash_log(exc)
    log_hint = f"\n\nDetails saved to:\n{log_path}" if log_path else ""
    show_fatal_error(
        "DLPulse Next",
        f"DLPulse Next could not start ({context}).\n\n{exc!s}{log_hint}",
    )


def apply_windows_packaged_env() -> None:
    if sys.platform != "win32":
        return
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        root = str(meipass)
        path = os.environ.get("PATH", "")
        if root not in path.split(os.pathsep):
            os.environ["PATH"] = root + os.pathsep + path
    os.environ.setdefault("PYTHONNET_RUNTIME", "coreclr")
    try:
        from dlpulse_next.windows_pythonnet import configure_windows_pythonnet

        configure_windows_pythonnet()
    except Exception:
        pass
