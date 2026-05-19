"""Linux AppImage / PyInstaller runtime helpers (system GTK/WebKit, optional GStreamer)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys


def is_linux_packaged() -> bool:
    if sys.platform != "linux":
        return False
    return bool(getattr(sys, "frozen", False) or os.environ.get("APPIMAGE"))


def gstreamer_element_available(name: str) -> bool:
    if shutil.which("gst-inspect-1.0") is None:
        return False
    env = os.environ.copy()
    for _p in (
        "/usr/lib/gstreamer-1.0",
        "/usr/lib64/gstreamer-1.0",
        "/usr/lib/x86_64-linux-gnu/gstreamer-1.0",
    ):
        if os.path.isdir(_p):
            env["GST_PLUGIN_SYSTEM_PATH"] = _p
            env.pop("GST_PLUGIN_PATH", None)
            break
    try:
        r = subprocess.run(
            ["gst-inspect-1.0", name],
            env=env,
            capture_output=True,
            timeout=8,
        )
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def mpv_available() -> bool:
    return shutil.which("mpv") is not None


def in_app_video_supported() -> bool:
    return gstreamer_element_available("appsink") and gstreamer_element_available("autoaudiosink")


def recommended_playback_mode() -> str:
    if in_app_video_supported():
        return "internal"
    if mpv_available() or shutil.which("vlc"):
        return "external"
    return "internal"


def apply_packaged_defaults() -> None:
    """Once per install: prefer external playback when GStreamer is unusable in WebKit."""
    if not is_linux_packaged():
        return
    from dlpulse_next.settings_store import _read_settings, _write_settings

    data = _read_settings()
    if data.get("linux_packaged_defaults_v1"):
        return
    mode = (data.get("playback_mode") or "internal").strip().lower()
    if mode not in ("internal", "external", "browser"):
        mode = "internal"
    if mode == "internal" and not in_app_video_supported():
        data["playback_mode"] = recommended_playback_mode()
    data["linux_packaged_defaults_v1"] = True
    _write_settings(data)


def runtime_info() -> dict:
    if not is_linux_packaged():
        return {}
    return {
        "packaged": True,
        "in_app_video": in_app_video_supported(),
        "mpv_available": mpv_available(),
        "recommended_playback": recommended_playback_mode(),
    }
