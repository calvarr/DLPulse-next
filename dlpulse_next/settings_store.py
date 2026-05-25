"""Persistent settings (download folder, players, cast) for DLPulse Next — replaces flet_app/download_dir."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

_CONFIG_DIR: Path | None = None
_cached_root: Path | None = None


def _config_dir() -> Path:
    global _CONFIG_DIR
    if _CONFIG_DIR is not None:
        return _CONFIG_DIR
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home()))).expanduser()
        _CONFIG_DIR = (base / "DLPulseNext").resolve()
    else:
        _CONFIG_DIR = (Path.home() / ".config" / "dlpulse-next").expanduser().resolve()
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        _CONFIG_DIR = Path(__file__).resolve().parent
    return _CONFIG_DIR


def _settings_path() -> Path:
    return _config_dir() / "settings.json"


def default_user_downloads_dir() -> Path:
    if sys.platform == "linux":
        try:
            out = subprocess.run(
                ["xdg-user-dir", "DOWNLOAD"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            p = (out.stdout or "").strip()
            if p and Path(p).is_dir():
                return Path(p).expanduser().resolve()
        except (OSError, subprocess.TimeoutExpired):
            pass
    home = Path.home()
    for name in ("Downloads", "Descărcări", "Téléchargements", "Загрузки"):
        cand = home / name
        if cand.is_dir():
            return cand.resolve()
    d = home / "Downloads"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return d.resolve()


def _read_settings() -> dict:
    try:
        p = _settings_path()
        if not p.is_file():
            return {}
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_settings(data: dict) -> None:
    try:
        _settings_path().write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def _load_saved_dir() -> Path | None:
    try:
        raw = (_read_settings().get("download_dir") or _read_settings().get("path") or "").strip()
        if not raw:
            return None
        return Path(raw).expanduser().resolve()
    except (OSError, ValueError):
        return None


def get_downloads_dir() -> Path:
    global _cached_root
    if _cached_root is not None:
        return _cached_root
    loaded = _load_saved_dir()
    _cached_root = loaded if loaded else default_user_downloads_dir()
    try:
        _cached_root.mkdir(parents=True, exist_ok=True)
    except OSError:
        _cached_root = default_user_downloads_dir()
        _cached_root.mkdir(parents=True, exist_ok=True)
    return _cached_root


def set_downloads_dir(path: Path) -> Path:
    global _cached_root
    p = path.expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    _cached_root = p
    data = _read_settings()
    data["download_dir"] = str(p)
    _write_settings(data)
    return p


def get_video_player_command() -> str:
    return (_read_settings().get("video_player") or "").strip()


def set_video_player_command(cmd: str) -> None:
    data = _read_settings()
    data["video_player"] = cmd.strip()
    if "download_dir" not in data:
        data["download_dir"] = str(get_downloads_dir())
    _write_settings(data)


def get_audio_player_command() -> str:
    data = _read_settings()
    a = (data.get("audio_player") or "").strip()
    if a:
        return a
    return (data.get("video_player") or "").strip()


def set_audio_player_command(cmd: str) -> None:
    data = _read_settings()
    data["audio_player"] = cmd.strip()
    if "download_dir" not in data:
        data["download_dir"] = str(get_downloads_dir())
    _write_settings(data)


def get_playback_mode() -> str:
    raw = _read_settings().get("playback_mode")
    mode = ("" if raw is None else str(raw)).strip().lower()
    if mode in ("external", "internal", "browser"):
        return mode
    return "internal"


def set_playback_mode(mode: str) -> None:
    value = (mode or "").strip().lower()
    if value not in ("external", "internal", "browser"):
        value = "internal"
    data = _read_settings()
    data["playback_mode"] = value
    if "download_dir" not in data:
        data["download_dir"] = str(get_downloads_dir())
    _write_settings(data)


def get_cast_discovery_wait_s() -> float:
    raw = _read_settings().get("cast_discovery_wait_s", 3)
    try:
        v = float(raw) if not isinstance(raw, str) else float(raw.strip())
        return max(0.5, min(v, 120.0))
    except (TypeError, ValueError):
        return 3.0


def set_cast_discovery_wait_s(seconds: float) -> None:
    data = _read_settings()
    data["cast_discovery_wait_s"] = max(0.5, min(float(seconds), 120.0))
    if "download_dir" not in data:
        data["download_dir"] = str(get_downloads_dir())
    _write_settings(data)


def get_ui_theme() -> str:
    raw = _read_settings().get("ui_theme")
    v = ("" if raw is None else str(raw)).strip().lower()
    if v in ("light", "dark"):
        return v
    return "dark"


def set_ui_theme(theme: str) -> None:
    value = (theme or "").strip().lower()
    if value not in ("light", "dark"):
        value = "dark"
    data = _read_settings()
    data["ui_theme"] = value
    if "download_dir" not in data:
        data["download_dir"] = str(get_downloads_dir())
    _write_settings(data)


def default_ui_launch_mode() -> str:
    """Fresh installs: browser on Windows (WebView2/.NET issues); native elsewhere."""
    return "browser" if sys.platform == "win32" else "native"


def get_ui_launch_mode() -> str:
    """How the desktop shell opens on launch: native window or default browser."""
    raw = _read_settings().get("ui_launch_mode")
    mode = ("" if raw is None else str(raw)).strip().lower()
    if mode in ("native", "browser"):
        return mode
    return default_ui_launch_mode()


def set_ui_launch_mode(mode: str) -> None:
    value = (mode or "").strip().lower()
    if value not in ("native", "browser"):
        value = default_ui_launch_mode()
    data = _read_settings()
    data["ui_launch_mode"] = value
    if "download_dir" not in data:
        data["download_dir"] = str(get_downloads_dir())
    _write_settings(data)


_YTDLP_CHECK_EVERY_N_LAUNCHES = 5
_YTDLP_RECHECK_DAYS = 7


def bump_app_launch_count() -> int:
    data = _read_settings()
    n = int(data.get("app_launch_count", 0)) + 1
    data["app_launch_count"] = n
    _write_settings(data)
    return n


def should_check_ytdlp_pypi() -> bool:
    data = _read_settings()
    n = int(data.get("app_launch_count", 0))
    last = float(data.get("ytdlp_pypi_last_check_ts", 0) or 0)
    now = time.time()
    if n > 0 and n % _YTDLP_CHECK_EVERY_N_LAUNCHES == 0:
        return True
    if last <= 0:
        return True
    if now - last >= _YTDLP_RECHECK_DAYS * 86400:
        return True
    return False


def mark_ytdlp_pypi_checked() -> None:
    data = _read_settings()
    data["ytdlp_pypi_last_check_ts"] = time.time()
    _write_settings(data)


def get_github_update_dismissed_main_sha() -> str | None:
    s = (_read_settings().get("github_update_dismissed_main_sha") or "").strip()
    return s[:40] if len(s) >= 7 else None


def set_github_update_dismissed_main_sha(sha: str) -> None:
    data = _read_settings()
    data["github_update_dismissed_main_sha"] = (sha or "").strip()[:40]
    if "download_dir" not in data:
        data["download_dir"] = str(get_downloads_dir())
    _write_settings(data)


def get_app_update_dismissed_key() -> str | None:
    s = (_read_settings().get("app_update_dismissed_key") or "").strip()
    return s[:80] if s else None


def set_app_update_dismissed_key(key: str) -> None:
    data = _read_settings()
    data["app_update_dismissed_key"] = (key or "").strip()[:80]
    if "download_dir" not in data:
        data["download_dir"] = str(get_downloads_dir())
    _write_settings(data)


def get_download_parallel() -> int:
    """How many videos to download at once (playlist / multi-select)."""
    try:
        n = int(_read_settings().get("download_parallel", 1))
    except (TypeError, ValueError):
        n = 1
    return max(1, min(n, 5))


def set_download_parallel(n: int) -> None:
    data = _read_settings()
    data["download_parallel"] = max(1, min(int(n), 5))
    if "download_dir" not in data:
        data["download_dir"] = str(get_downloads_dir())
    _write_settings(data)


def get_use_aria2c() -> bool:
    return bool(_read_settings().get("use_aria2c"))


def set_use_aria2c(enabled: bool) -> None:
    data = _read_settings()
    data["use_aria2c"] = bool(enabled)
    if "download_dir" not in data:
        data["download_dir"] = str(get_downloads_dir())
    _write_settings(data)


def get_aria2c_connections() -> int:
    try:
        n = int(_read_settings().get("aria2c_connections", 16))
    except (TypeError, ValueError):
        n = 16
    return max(1, min(n, 32))


def set_aria2c_connections(n: int) -> None:
    data = _read_settings()
    data["aria2c_connections"] = max(1, min(int(n), 32))
    if "download_dir" not in data:
        data["download_dir"] = str(get_downloads_dir())
    _write_settings(data)


def get_download_rate_limit_bps() -> int:
    """0 = no limit. Stored setting is megabytes per second for the UI."""
    try:
        mbps = float(_read_settings().get("download_rate_limit_mbps", 0))
    except (TypeError, ValueError):
        mbps = 0.0
    if mbps <= 0:
        return 0
    return int(mbps * 1_000_000)


def get_download_rate_limit_mbps() -> float:
    bps = get_download_rate_limit_bps()
    return 0.0 if bps <= 0 else bps / 1_000_000


def set_download_rate_limit_mbps(mbps: float) -> None:
    data = _read_settings()
    v = max(0.0, float(mbps))
    data["download_rate_limit_mbps"] = v
    if "download_dir" not in data:
        data["download_dir"] = str(get_downloads_dir())
    _write_settings(data)
