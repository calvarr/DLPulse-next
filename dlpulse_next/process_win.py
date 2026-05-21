"""Windows: hide console windows for child processes (ffmpeg, yt-dlp tools)."""

from __future__ import annotations

import subprocess
import sys
import threading

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

_child_lock = threading.Lock()
_child_procs: list[subprocess.Popen] = []


def _startupinfo_hide() -> subprocess.STARTUPINFO | None:
    if sys.platform != "win32":
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    return si


def popen_kwargs(**extra: object) -> dict:
    """Extra keyword args for ``subprocess.Popen`` (no console on Windows)."""
    kw = dict(extra)
    if sys.platform == "win32":
        kw["creationflags"] = int(kw.get("creationflags", 0)) | _CREATE_NO_WINDOW
        if "startupinfo" not in kw:
            si = _startupinfo_hide()
            if si is not None:
                kw["startupinfo"] = si
    return kw


def run_kwargs(**extra: object) -> dict:
    """Extra keyword args for ``subprocess.run`` (no console on Windows)."""
    return popen_kwargs(**extra)


def register_child_process(proc: subprocess.Popen) -> None:
    with _child_lock:
        _child_procs[:] = [p for p in _child_procs if p.poll() is None]
        _child_procs.append(proc)


def unregister_child_process(proc: subprocess.Popen) -> None:
    with _child_lock:
        try:
            _child_procs.remove(proc)
        except ValueError:
            pass


def terminate_child_processes() -> None:
    """Kill tracked ffmpeg / tool children (e.g. on app exit)."""
    with _child_lock:
        snap = list(_child_procs)
        _child_procs.clear()
    for proc in snap:
        if proc.poll() is not None:
            continue
        try:
            proc.terminate()
        except OSError:
            pass
    for proc in snap:
        if proc.poll() is not None:
            continue
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except OSError:
                pass


def apply_ytdlp_hide_console() -> None:
    """Patch yt-dlp so ffmpeg/postprocessors do not spawn visible consoles."""
    if sys.platform != "win32":
        return
    try:
        from yt_dlp import utils as ytu
    except ImportError:
        return
    if getattr(ytu, "_dlpulse_hide_console", False):
        return
    real_popen = ytu.Popen

    def _popen(*args, **kwargs):
        kwargs.setdefault("creationflags", 0)
        kwargs["creationflags"] = int(kwargs["creationflags"]) | _CREATE_NO_WINDOW
        if "startupinfo" not in kwargs:
            si = _startupinfo_hide()
            if si is not None:
                kwargs["startupinfo"] = si
        return real_popen(*args, **kwargs)

    ytu.Popen = _popen
    ytu._dlpulse_hide_console = True
