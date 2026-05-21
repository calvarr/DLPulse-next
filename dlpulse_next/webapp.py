from __future__ import annotations

import sys
from pathlib import Path

# Allow running this file directly: ``python3 dlpulse_next/webapp.py``
# (adds the project root that *contains* the ``dlpulse_next`` package to sys.path).
if __name__ == "__main__":
    _repo = Path(__file__).resolve().parent.parent
    _s = str(_repo)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from urllib.parse import quote

from flask import Flask, Response, jsonify, request, send_file, send_from_directory

import atexit
import logging
import os
import shlex
import shutil
import subprocess
import tempfile
import threading
import uuid

from dlpulse_next.cast_http import (
    get_cast_server_port,
    guess_mime_for_cast,
    is_cast_server_running,
    media_url,
    internal_relay_urls_for_pages,
    prewarm_remote_stream_extractions,
    register_media_path,
    start_cast_server,
    stop_cast_server,
    validate_chromecast_remote_stream_url,
)
from dlpulse_next.chromecast_helper import (
    discover_chromecasts,
    get_lan_ip,
    media_progress,
    pause as cast_pause,
    play as cast_play_receiver,
    play_stream_queue_on_cast,
    play_stream_queue_on_casts,
    play_url,
    play_url_to_casts,
    queue_set_repeat_mode,
    queue_set_shuffle,
    seek_media,
    set_receiver_volume,
    stop_last_cast,
    stop_projection,
)
from dlpulse_next.settings_store import (
    bump_app_launch_count,
    get_aria2c_connections,
    get_audio_player_command,
    get_cast_discovery_wait_s,
    get_download_parallel,
    get_download_rate_limit_mbps,
    get_downloads_dir,
    get_app_update_dismissed_key,
    get_github_update_dismissed_main_sha,
    get_playback_mode,
    get_ui_launch_mode,
    get_ui_theme,
    get_use_aria2c,
    get_video_player_command,
    set_aria2c_connections,
    set_audio_player_command,
    set_cast_discovery_wait_s,
    set_download_parallel,
    set_download_rate_limit_mbps,
    set_downloads_dir,
    set_app_update_dismissed_key,
    set_github_update_dismissed_main_sha,
    set_playback_mode,
    set_ui_launch_mode,
    set_ui_theme,
    set_use_aria2c,
    set_video_player_command,
)
from dlpulse_next.yt_core import (
    FORMAT_PRESETS,
    detect_content_type,
    extract_url_info,
    fetch_playlist_entries,
    get_format_preset,
    run_download,
    youtube_url_for_single_video_download,
)
from dlpulse_next.library_scan import scan_library
from dlpulse_next.file_browser import (
    browse as fs_browse,
    delete_item as fs_delete,
    delete_items as fs_delete_items,
    mkdir as fs_mkdir,
    rename_item as fs_rename,
)
from dlpulse_next.ffmpeg_tools import aria2c_available, aria2c_is_bundled, ffmpeg_available
from dlpulse_next.native_dialogs import pick_folder_dialog
from dlpulse_next.search_logic import preset_requires_ffmpeg_conversion, resolve_search_or_url

_log = logging.getLogger(__name__)
_PKG = Path(__file__).resolve().parent

_DONATE_BMC_URL = "https://buymeacoffee.com/medcodex"
_DONATE_BTC = "bc1q8gv3zue7wtem279rqz7rj405qftpu9855k2l2s"
_REPO_ROOT = _PKG.parent.parent


def _bundled_donate_dir() -> Path:
    return _PKG / "static" / "donate"


def _donate_cofe_png_path() -> Path | None:
    d = _bundled_donate_dir()
    for candidate in (
        d / "cofe.png",
        d / "bmc.png",
        _REPO_ROOT / "yt" / "flet_app" / "cofe.png",
    ):
        if candidate.is_file():
            return candidate
    return None


def _flet_btc_image_path() -> Path | None:
    d = _bundled_donate_dir()
    for name in ("BTC.jpeg", "BTC.jpg", "btc.jpeg", "btc.png"):
        p = d / name
        if p.is_file():
            return p
    base = _REPO_ROOT / "yt"
    for name in ("BTC.jpeg", "BTC.jpg", "btc.jpeg"):
        p = base / name
        if p.is_file():
            return p
    return None


def _donate_qr_svg_bytes(payload: str) -> bytes:
    import io

    import qrcode
    import qrcode.constants
    import qrcode.image.svg

    buf = io.BytesIO()
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
    img.save(buf)
    return buf.getvalue()

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
_cast_devices: list = []
_cast_lock = threading.Lock()
_cast_last_play_idxs: list[int] = []
_cast_repeat_cycle: int = 0
_lib_state_lock = threading.Lock()
_lib_view_dir: Path | None = None
_lib_session_dir: Path | None = None


def _json_error(message: str, code: int = 400):
    return jsonify({"ok": False, "error": message}), code


def _cc_indices_from_request(data: dict, devs: list) -> list[int]:
    """Flet-style: explicit ``device_indices`` / ``device_index``, else last successful cast targets."""
    global _cast_last_play_idxs
    raw = data.get("device_indices")
    if isinstance(raw, list) and len(raw) > 0:
        out: list[int] = []
        seen: set[int] = set()
        for x in raw:
            try:
                i = int(x)
            except (TypeError, ValueError):
                continue
            if 0 <= i < len(devs) and i not in seen:
                seen.add(i)
                out.append(i)
        if out:
            return out
    try:
        j = int(data.get("device_index", -1))
    except (TypeError, ValueError):
        j = -1
    if 0 <= j < len(devs):
        return [j]
    return [i for i in _cast_last_play_idxs if 0 <= i < len(devs)]


def _ensure_stream_server() -> int:
    if not is_cast_server_running():
        start_cast_server("0.0.0.0", 0)
    port = get_cast_server_port()
    if port <= 0:
        raise RuntimeError("Local stream server failed to start.")
    return port


def _default_player_argv(for_audio: bool) -> list[str] | None:
    cmd = (get_audio_player_command() if for_audio else get_video_player_command()).strip()
    if cmd:
        return shlex.split(cmd, posix=os.name != "nt")
    if sys.platform == "win32":
        for p in (
            r"C:\Program Files\mpv\mpv.exe",
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        ):
            if os.path.isfile(p):
                return [p]
    if sys.platform == "darwin":
        mpv = "/opt/homebrew/bin/mpv"
        if os.path.isfile(mpv):
            return [mpv]
        mpv2 = "/usr/local/bin/mpv"
        if os.path.isfile(mpv2):
            return [mpv2]
        vlc = "/Applications/VLC.app/Contents/MacOS/VLC"
        if os.path.isfile(vlc):
            return [vlc]
    for name in ("mpv", "vlc"):
        found = shutil_which(name)
        if found:
            return [found]
    return None


def shutil_which(name: str) -> str | None:
    import shutil

    return shutil.which(name)


_external_player_lock = threading.Lock()
_external_player_procs: list[subprocess.Popen] = []


def _register_external_player(proc: subprocess.Popen) -> None:
    """Track Popen so we can terminate on app exit (see ``terminate_external_players``)."""
    with _external_player_lock:
        _external_player_procs[:] = [p for p in _external_player_procs if p.poll() is None]
        _external_player_procs.append(proc)


def terminate_external_players() -> None:
    """SIGTERM/SIGKILL child players started from this process (mpv, vlc, …)."""
    with _external_player_lock:
        snap = list(_external_player_procs)
        _external_player_procs.clear()
    for p in snap:
        if p.poll() is not None:
            continue
        try:
            p.terminate()
        except OSError:
            pass
    for p in snap:
        if p.poll() is not None:
            continue
        try:
            p.wait(timeout=4.0)
        except subprocess.TimeoutExpired:
            try:
                p.kill()
            except OSError:
                pass


def _maybe_mpv_force_gui_argv(argv: list[str]) -> list[str]:
    """If launcher is mpv, force a visible window and a non-null VO (many configs use vo=null)."""
    if not argv:
        return argv
    exe = Path(argv[0]).name.lower()
    if exe not in ("mpv", "mpv.exe"):
        return argv
    tail = argv[1:]
    joined = " ".join(tail)
    if "--force-window" in joined:
        return argv
    if "--no-video" in joined or "--vo=null" in joined.replace(" ", ""):
        return argv
    insert: list[str] = ["--force-window=yes"]
    if "--vo" not in joined and "--profile" not in joined:
        insert.append("--vo=gpu,x11,wayland,sdl")
    return [argv[0], *insert, *tail]


def _spawn_player(argv: list[str], target: str) -> None:
    argv = list(argv)
    if "{}" in " ".join(argv):
        line = " ".join(argv).replace("{}", target)
        argv = shlex.split(line, posix=os.name != "nt")
    else:
        argv = [*argv, target]
    argv = _maybe_mpv_force_gui_argv(argv)
    kw: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name != "nt":
        kw["start_new_session"] = True
    proc = subprocess.Popen(argv, **kw)
    _register_external_player(proc)


def _safe_under_downloads(rel: str) -> Path | None:
    root = get_downloads_dir().resolve()
    if rel.strip() in ("", ".", "/"):
        return root
    p = (root / rel.lstrip("/").replace("\\", "/")).resolve()
    if not p.is_relative_to(root):
        return None
    return p


def _resolve_download_output_dir(raw: str | None) -> Path:
    """Session folder (Flet ``search_session_dir``) or default Settings download dir."""
    if raw and str(raw).strip():
        p = Path(str(raw).strip()).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    return get_downloads_dir()


def _get_library_roots() -> list[Path]:
    with _lib_state_lock:
        vd = _lib_view_dir
        sd = _lib_session_dir
    roots: list[Path] = []
    if vd is not None:
        try:
            roots.append(vd.expanduser().resolve())
        except OSError:
            roots.append(vd.expanduser())
        return roots
    try:
        r0 = get_downloads_dir().expanduser().resolve()
    except OSError:
        r0 = get_downloads_dir().expanduser()
    roots.append(r0)
    if sd is not None:
        try:
            r1 = sd.expanduser().resolve()
        except OSError:
            r1 = sd.expanduser()
        if r1 != r0:
            roots.append(r1)
    return roots


def _path_allowed_for_library(p: Path) -> bool:
    try:
        pr = p.expanduser().resolve()
    except OSError:
        pr = p.expanduser()
    if not pr.is_file():
        return False
    for root in _get_library_roots():
        try:
            pr.relative_to(root.resolve())
            return True
        except ValueError:
            try:
                pr.relative_to(root)
                return True
            except ValueError:
                continue
    return False


def _resolve_library_path_arg(raw: str) -> Path | None:
    """Relative path under Settings downloads, or absolute path if under library roots."""
    s = (raw or "").strip()
    if not s:
        return None
    if s.startswith("/") or (len(s) > 2 and s[1] == ":"):  # POSIX or Windows drive
        p = Path(s).expanduser()
        return p if _path_allowed_for_library(p) else None
    return _safe_under_downloads(s)


_AUDIO_EXTS = frozenset({".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wav", ".wma", ".m4b", ".alac"})


def _is_audio_path(p: Path) -> bool:
    return p.suffix.lower() in _AUDIO_EXTS


def _write_temp_m3u_uris(uris: list[str], titles: list[str]) -> Path:
    lines = [u.strip() for u in uris if u.strip()]
    if not lines:
        raise ValueError("No playlist entries.")
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        suffix=".m3u",
        prefix="dlpulse_pl_",
        delete=False,
    )
    out_path = Path(tmp.name)
    try:
        tmp.write("#EXTM3U\n")
        for i, line in enumerate(lines):
            label = (titles[i] if i < len(titles) else f"Track {i + 1}")[:240]
            tmp.write(f"#EXTINF:-1,{label}\n")
            tmp.write(line + "\n")
        tmp.close()
        return out_path
    except Exception:
        tmp.close()
        try:
            out_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _play_library_paths(paths: list[Path]) -> None:
    resolved = [p.expanduser().resolve() for p in paths]
    for p in resolved:
        if not p.is_file():
            raise OSError(f"Not found: {p}")
    if len(resolved) == 1:
        p = resolved[0]
        argv = _default_player_argv(_is_audio_path(p))
        if not argv:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(p)], **{"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL})
            elif sys.platform == "win32":
                os.startfile(str(p))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(p)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        _spawn_player(argv, str(p))
        return
    pl = _write_temp_m3u_uris([p.as_uri() for p in resolved], [p.name for p in resolved])
    all_audio = all(_is_audio_path(p) for p in resolved)
    argv = _default_player_argv(all_audio)
    if not argv:
        raise ValueError("No player command for multi-file playlist.")
    _spawn_player(argv, str(pl))


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(_PKG / "static"), static_url_path="/static")

    @app.route("/")
    def index():
        return send_from_directory(_PKG / "static", "index.html")

    @app.get("/api/donate/qr.svg")
    def api_donate_qr_svg():
        k = (request.args.get("kind") or "bmc").lower().strip()
        payload = _DONATE_BTC if k == "btc" else _DONATE_BMC_URL
        try:
            body = _donate_qr_svg_bytes(payload)
        except Exception as ex:
            _log.warning("donate QR SVG failed: %s", ex)
            return _json_error("QR generation failed", 500)
        return Response(body, mimetype="image/svg+xml")

    @app.get("/api/donate/asset/<name>")
    def api_donate_asset(name: str):
        key = (name or "").strip().lower()
        p: Path | None = None
        mime = "application/octet-stream"
        if key in ("coffee", "cofe", "bmc", "bmc_qr"):
            p = _donate_cofe_png_path()
            mime = "image/png"
        elif key in ("btc", "btc_qr"):
            p = _flet_btc_image_path()
            if p is not None:
                suf = p.suffix.lower()
                mime = "image/jpeg" if suf in (".jpg", ".jpeg") else "image/png"
        if p is None or not p.is_file():
            return _json_error("Not found", 404)
        return send_file(p, mimetype=mime)

    @app.get("/api/version")
    def api_version():
        from dlpulse_next.github_update import (
            GITHUB_RELEASES_URL,
            commit_page_url,
            fetch_latest_github_release,
            get_build_release_tag,
            get_local_commit_sha,
        )
        from dlpulse_next.ytdlp_update import get_installed_ytdlp_version

        commit = get_local_commit_sha()
        release_tag = get_build_release_tag()
        rel = fetch_latest_github_release()
        return jsonify(
            {
                "ok": True,
                "release_tag": release_tag,
                "commit": commit,
                "commit_url": commit_page_url(commit) if commit else None,
                "releases_url": GITHUB_RELEASES_URL,
                "latest_release_tag": (rel or {}).get("tag_name") if rel else None,
                "latest_release_url": (rel or {}).get("html_url") if rel else None,
                "bundled": {
                    "ffmpeg": ffmpeg_available(),
                    "aria2c": aria2c_available(),
                    "aria2c_bundled": aria2c_is_bundled(),
                    "ytdlp": get_installed_ytdlp_version(),
                },
            }
        )

    @app.get("/api/format_presets")
    def api_format_presets():
        out = [{"index": i, "label": row[0]} for i, row in enumerate(FORMAT_PRESETS)]
        return jsonify({"ok": True, "presets": out})

    @app.get("/api/settings")
    def api_settings_get():
        root = get_downloads_dir()
        aria2_on = get_use_aria2c()
        payload: dict = {
            "ok": True,
            "download_dir": str(root),
            "video_player": get_video_player_command(),
            "audio_player": get_audio_player_command(),
            "playback_mode": get_playback_mode(),
            "cast_discovery_wait_s": get_cast_discovery_wait_s(),
            "ui_theme": get_ui_theme(),
            "ui_launch_mode": get_ui_launch_mode(),
            "download_parallel": get_download_parallel(),
            "use_aria2c": aria2_on,
            "aria2c_connections": get_aria2c_connections(),
            "aria2c_available": aria2c_available(),
            "aria2c_bundled": aria2c_is_bundled(),
            "download_rate_limit_mbps": get_download_rate_limit_mbps(),
        }
        if sys.platform == "linux":
            from dlpulse_next.linux_packaged import runtime_info

            payload["linux_runtime"] = runtime_info()
        return jsonify(payload)

    @app.post("/api/settings")
    def api_settings_post():
        data = request.get_json(force=True, silent=True) or {}
        if "download_dir" in data and str(data["download_dir"]).strip():
            set_downloads_dir(Path(str(data["download_dir"]).strip()))
        if "video_player" in data:
            set_video_player_command(str(data.get("video_player") or ""))
        if "audio_player" in data:
            set_audio_player_command(str(data.get("audio_player") or ""))
        if "playback_mode" in data:
            set_playback_mode(str(data.get("playback_mode") or "internal"))
        if "cast_discovery_wait_s" in data:
            try:
                set_cast_discovery_wait_s(float(data["cast_discovery_wait_s"]))
            except (TypeError, ValueError):
                pass
        if "ui_theme" in data:
            set_ui_theme(str(data.get("ui_theme") or "dark"))
        if "ui_launch_mode" in data:
            set_ui_launch_mode(str(data.get("ui_launch_mode") or "native"))
        if "download_parallel" in data:
            try:
                set_download_parallel(int(data["download_parallel"]))
            except (TypeError, ValueError):
                pass
        if "use_aria2c" in data:
            set_use_aria2c(bool(data.get("use_aria2c")))
        if "aria2c_connections" in data:
            try:
                set_aria2c_connections(int(data["aria2c_connections"]))
            except (TypeError, ValueError):
                pass
        if "download_rate_limit_mbps" in data:
            try:
                set_download_rate_limit_mbps(float(data["download_rate_limit_mbps"]))
            except (TypeError, ValueError):
                pass
        return api_settings_get()

    @app.post("/api/probe")
    def api_probe():
        data = request.get_json(force=True, silent=True) or {}
        url = str(data.get("url") or "").strip()
        if not url:
            return _json_error("Missing url")
        info = extract_url_info(url)
        if not info:
            return _json_error("Could not read URL (yt-dlp).", 422)
        ctype, desc = detect_content_type(info)
        return jsonify({"ok": True, "type": ctype, "description": desc, "title": info.get("title")})

    @app.get("/api/ffmpeg")
    def api_ffmpeg():
        return jsonify({"ok": True, "available": bool(ffmpeg_available())})

    @app.post("/api/pick_folder")
    def api_pick_folder():
        """Legacy native picker; UI uses ``/api/fs/browse`` in-app browser instead."""
        data = request.get_json(force=True, silent=True) or {}
        start = str(data.get("start") or "").strip()
        base = get_downloads_dir()
        initial = start if start and os.path.isdir(start) else str(base)
        path = pick_folder_dialog(initial, title=str(data.get("title") or "Choose download folder"))
        return jsonify({"ok": True, "path": path})

    @app.post("/api/fs/browse")
    def api_fs_browse():
        data = request.get_json(force=True, silent=True) or {}
        path = str(data.get("path") or "").strip() or None
        start = str(data.get("initial") or data.get("start") or "").strip() or None
        if not start:
            start = str(get_downloads_dir())
        show_all = bool(data.get("show_all_files"))
        out = fs_browse(path, initial=start, media_only=not show_all)
        if not out.get("ok"):
            return jsonify(out), 400
        return jsonify(out)

    @app.post("/api/fs/mkdir")
    def api_fs_mkdir():
        data = request.get_json(force=True, silent=True) or {}
        parent = str(data.get("parent") or data.get("path") or "").strip()
        name = str(data.get("name") or "").strip()
        if not parent or not name:
            return _json_error("parent and name required", 400)
        out = fs_mkdir(parent, name)
        if not out.get("ok"):
            return jsonify(out), 400
        return jsonify(out)

    @app.post("/api/fs/rename")
    def api_fs_rename():
        data = request.get_json(force=True, silent=True) or {}
        target = str(data.get("path") or "").strip()
        new_name = str(data.get("new_name") or "").strip()
        if not target or not new_name:
            return _json_error("path and new_name required", 400)
        out = fs_rename(target, new_name)
        if not out.get("ok"):
            return jsonify(out), 400
        return jsonify(out)

    @app.post("/api/fs/delete")
    def api_fs_delete():
        data = request.get_json(force=True, silent=True) or {}
        target = str(data.get("path") or "").strip()
        if not target:
            return _json_error("path required", 400)
        out = fs_delete(target)
        if not out.get("ok"):
            return jsonify(out), 400
        return jsonify(out)

    @app.post("/api/fs/delete_batch")
    def api_fs_delete_batch():
        data = request.get_json(force=True, silent=True) or {}
        raw = data.get("paths") or []
        if not isinstance(raw, list) or not raw:
            return _json_error("paths required", 400)
        paths = [str(p).strip() for p in raw if str(p).strip()]
        if not paths:
            return _json_error("paths required", 400)
        out = fs_delete_items(paths)
        status = 200 if out.get("deleted", 0) else 400
        return jsonify(out), status

    @app.post("/api/fs/reveal")
    def api_fs_reveal():
        data = request.get_json(force=True, silent=True) or {}
        raw = str(data.get("path") or "").strip()
        if not raw:
            return _json_error("path required", 400)
        p = Path(raw).expanduser()
        try:
            p = p.resolve()
        except OSError as e:
            return _json_error(str(e), 400)
        if not p.exists():
            return _json_error("Not found", 404)
        try:
            if p.is_dir():
                target = p
                if sys.platform == "darwin":
                    subprocess.Popen(["open", str(target)], stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif sys.platform == "win32":
                    subprocess.Popen(["explorer", str(target)], stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.Popen(["xdg-open", str(target)], stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(p)], stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif sys.platform == "win32":
                subprocess.Popen(
                    ["explorer", "/select,", str(p.resolve())], stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            else:
                subprocess.Popen(["xdg-open", str(p.parent)], stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            return _json_error(str(e), 500)
        return jsonify({"ok": True})

    @app.post("/api/resolve")
    def api_resolve():
        data = request.get_json(force=True, silent=True) or {}
        text = str(data.get("text") or data.get("q") or "").strip()
        yt = bool(data.get("youtube", True))
        sc = bool(data.get("soundcloud", False))
        try:
            mx = int(data.get("max_per_source", 12))
        except (TypeError, ValueError):
            mx = 12
        mx = max(1, min(mx, 50))
        return jsonify(resolve_search_or_url(text, youtube=yt, soundcloud=sc, max_per_source=mx))

    @app.post("/api/search")
    def api_search():
        data = request.get_json(force=True, silent=True) or {}
        q = str(data.get("q") or "").strip()
        if not q:
            return _json_error("Missing q")
        yt = bool(data.get("youtube", True))
        sc = bool(data.get("soundcloud", False))
        try:
            mx = int(data.get("max_per_source", 15))
        except (TypeError, ValueError):
            mx = 15
        mx = max(1, min(mx, 50))
        r = resolve_search_or_url(q, youtube=yt, soundcloud=sc, max_per_source=mx)
        if not r.get("ok", True):
            return jsonify(r), 422
        return jsonify(
            {
                "ok": True,
                "hits": r.get("items", []),
                "sources": r.get("sources_used", []),
                "kind": r.get("kind"),
                "message": r.get("message", ""),
            }
        )

    @app.post("/api/playlist")
    def api_playlist():
        data = request.get_json(force=True, silent=True) or {}
        url = str(data.get("url") or "").strip()
        normalize = bool(data.get("normalize_url", True))
        if not url:
            return _json_error("Missing url")
        entries, err = fetch_playlist_entries(url, 500, normalize_url=normalize)
        if err:
            return jsonify({"ok": False, "error": err, "entries": []}), 422
        return jsonify({"ok": True, "entries": entries})

    @app.post("/api/download")
    def api_download():
        data = request.get_json(force=True, silent=True) or {}
        url = str(data.get("url") or "").strip()
        try:
            preset = int(data.get("format_preset_index", 0))
        except (TypeError, ValueError):
            preset = 0
        # Flet ``on_dl_results`` always passes ``no_playlist=True`` for grid downloads.
        no_pl = bool(data.get("no_playlist", True))
        cover = bool(data.get("download_cover", False))
        if not url:
            return _json_error("Missing url")
        if preset_requires_ffmpeg_conversion(preset) and not ffmpeg_available():
            return _json_error(
                "This audio preset needs ffmpeg (MP3/M4A extraction). Install ffmpeg or use a build that bundles it.",
                422,
            )
        spec = get_format_preset(preset)
        if not spec:
            return _json_error("Invalid preset index")
        fmt, opts_extra = spec
        job_id = uuid.uuid4().hex
        out_dir = str(_resolve_download_output_dir(data.get("output_dir")))

        def worker() -> None:
            def cb(p: dict) -> None:
                with _jobs_lock:
                    if job_id in _jobs:
                        _jobs[job_id]["progress"] = p

            with _jobs_lock:
                _jobs[job_id] = {"status": "running", "progress": {}, "files": [], "error": None}
            try:
                ok, files, err = run_download(
                    url, fmt, opts_extra, out_dir, no_playlist=no_pl, download_cover=cover, progress_callback=cb
                )
                with _jobs_lock:
                    _jobs[job_id]["status"] = "done" if ok else "error"
                    _jobs[job_id]["files"] = files
                    _jobs[job_id]["error"] = err
            except Exception as e:
                with _jobs_lock:
                    _jobs[job_id]["status"] = "error"
                    _jobs[job_id]["error"] = str(e)

        threading.Thread(target=worker, daemon=True, name=f"dl-{job_id[:8]}").start()
        return jsonify({"ok": True, "job_id": job_id})

    @app.get("/api/download/<job_id>")
    def api_download_status(job_id: str):
        with _jobs_lock:
            j = _jobs.get(job_id)
        if not j:
            return _json_error("Unknown job", 404)
        return jsonify({"ok": True, **j})

    @app.post("/api/stream_urls")
    def api_stream_urls():
        data = request.get_json(force=True, silent=True) or {}
        raw = data.get("urls") or []
        clean = [youtube_url_for_single_video_download(str(u).strip()) for u in raw if str(u).strip()]
        if not clean:
            return _json_error("No urls")
        try:
            port = _ensure_stream_server()
        except Exception as e:
            return _json_error(str(e), 500)
        host = str(data.get("host") or "127.0.0.1")

        try:
            rel = internal_relay_urls_for_pages(clean, host, port)
        except Exception as e:
            return _json_error(str(e), 500)
        if not rel:
            return _json_error("Could not resolve a stream URL", 502)

        return jsonify({"ok": True, "urls": rel, "port": port})

    @app.get("/api/library")
    def api_library():
        with _lib_state_lock:
            vd = _lib_view_dir
            sd = _lib_session_dir
        dd = get_downloads_dir()
        show_all = request.args.get("show_all_files", "").lower() in ("1", "true", "yes")
        items = scan_library(dd, session_dir=sd, view_dir=vd, media_only=not show_all)
        empty_hint: dict | None = None
        if not items:
            empty_hint = {"title": "No files.", "lines": []}
        return jsonify(
            {
                "ok": True,
                "downloads_dir": str(dd),
                "view_dir": str(vd) if vd else None,
                "session_dir": str(sd) if sd else None,
                "browsing": vd is not None,
                "items": items,
                "empty_hint": empty_hint,
            }
        )

    @app.post("/api/library/view")
    def api_library_view():
        global _lib_view_dir
        data = request.get_json(force=True, silent=True) or {}
        raw = data.get("path")
        with _lib_state_lock:
            if raw is None or (isinstance(raw, str) and not str(raw).strip()):
                _lib_view_dir = None
            else:
                p = Path(str(raw).strip()).expanduser().resolve()
                if not p.is_dir():
                    return _json_error("Not a directory", 400)
                _lib_view_dir = p
        return jsonify({"ok": True, "view_dir": str(_lib_view_dir) if _lib_view_dir else None})

    @app.post("/api/library/session")
    def api_library_session():
        global _lib_session_dir
        data = request.get_json(force=True, silent=True) or {}
        raw = data.get("path")
        with _lib_state_lock:
            if raw is None or (isinstance(raw, str) and not str(raw).strip()):
                _lib_session_dir = None
            else:
                p = Path(str(raw).strip()).expanduser().resolve()
                p.mkdir(parents=True, exist_ok=True)
                _lib_session_dir = p
        return jsonify({"ok": True, "session_dir": str(_lib_session_dir) if _lib_session_dir else None})

    @app.post("/api/library/rename")
    def api_library_rename():
        data = request.get_json(force=True, silent=True) or {}
        src = str(data.get("path") or "").strip()
        new_name = (data.get("new_name") or "").strip()
        if not new_name or ".." in new_name or "/" in new_name or "\\" in new_name:
            return _json_error("Invalid filename", 400)
        p = _resolve_library_path_arg(src)
        if p is None or not p.is_file():
            return _json_error("File not found", 404)
        dest = p.parent / new_name
        if dest.exists():
            return _json_error("A file with that name already exists.", 409)
        try:
            p.rename(dest)
        except OSError as e:
            return _json_error(str(e), 500)
        return jsonify({"ok": True})

    @app.post("/api/library/delete")
    def api_library_delete():
        data = request.get_json(force=True, silent=True) or {}
        paths_raw = data.get("paths") or []
        deleted = 0
        last_err: str | None = None
        for s in paths_raw:
            p = _resolve_library_path_arg(str(s).strip())
            if p is None or not p.is_file():
                last_err = "Invalid path"
                continue
            try:
                p.unlink()
                deleted += 1
            except OSError as e:
                last_err = str(e)
        return jsonify({"ok": True, "deleted": deleted, "error": last_err})

    @app.post("/api/library/internal_stream_urls")
    def api_library_internal_stream_urls():
        data = request.get_json(force=True, silent=True) or {}
        paths_raw = data.get("paths") or []
        plist: list[Path] = []
        for s in paths_raw:
            p = _resolve_library_path_arg(str(s).strip())
            if p is not None and p.is_file():
                plist.append(p)
        if not plist:
            return _json_error("No valid files", 404)
        try:
            port = _ensure_stream_server()
        except Exception as e:
            return _json_error(str(e), 500)
        host = str(data.get("host") or "127.0.0.1")
        urls: list[str] = []
        labels: list[str] = []
        for p in plist:
            rel = register_media_path(p.resolve())
            urls.append(media_url(rel, host, port))
            labels.append(p.name)
        return jsonify({"ok": True, "urls": urls, "labels": labels, "port": port})

    @app.post("/api/library/play")
    def api_library_play():
        data = request.get_json(force=True, silent=True) or {}
        paths_raw = data.get("paths") or []
        plist: list[Path] = []
        for s in paths_raw:
            p = _resolve_library_path_arg(str(s).strip())
            if p is not None and p.is_file():
                plist.append(p)
        if not plist:
            return _json_error("No valid files", 404)
        try:
            _play_library_paths(plist)
        except (OSError, ValueError) as e:
            return _json_error(str(e), 500)
        return jsonify({"ok": True})

    @app.post("/api/library/cast_prepare")
    def api_library_cast_prepare():
        data = request.get_json(force=True, silent=True) or {}
        paths_raw = data.get("paths") or []
        out: list[dict] = []
        for s in paths_raw:
            p = _resolve_library_path_arg(str(s).strip())
            if p is not None and p.is_file():
                tok = register_media_path(p.resolve())
                out.append({"token": tok, "label": p.name})
        if not out:
            return _json_error("No valid files", 404)
        return jsonify({"ok": True, "prepared": out})

    @app.post("/api/reveal")
    def api_reveal():
        data = request.get_json(force=True, silent=True) or {}
        rel = str(data.get("path") or "").strip()
        p = _resolve_library_path_arg(rel)
        if p is None or not p.exists():
            return _json_error("Invalid path", 404)
        try:
            if p.is_dir():
                target = p
                if sys.platform == "darwin":
                    subprocess.Popen(["open", str(target)], stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif sys.platform == "win32":
                    subprocess.Popen(["explorer", str(target)], stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.Popen(["xdg-open", str(target)], stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(p)], stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif sys.platform == "win32":
                subprocess.Popen(
                    ["explorer", "/select,", str(p.resolve())], stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            else:
                subprocess.Popen(["xdg-open", str(p.parent)], stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            return _json_error(str(e), 500)
        return jsonify({"ok": True})

    @app.post("/api/play_file")
    def api_play_file():
        data = request.get_json(force=True, silent=True) or {}
        rel = str(data.get("path") or "").strip()
        p = _resolve_library_path_arg(rel)
        if p is None or not p.is_file():
            return _json_error("File not found", 404)
        argv = _default_player_argv(_is_audio_path(p))
        if not argv:
            return _json_error("No player configured and none found in PATH.", 422)
        try:
            _spawn_player(argv, str(p.resolve()))
        except OSError as e:
            return _json_error(str(e), 500)
        return jsonify({"ok": True})

    @app.post("/api/chromecast/discover")
    def api_cc_discover():
        data = request.get_json(force=True, silent=True) or {}
        wait = float(data.get("wait_s") or get_cast_discovery_wait_s())
        wait = max(0.5, min(wait, 120.0))

        def run():
            return discover_chromecasts(wait)

        try:
            devices = run()
        except Exception as e:
            return _json_error(str(e), 500)
        global _cast_devices, _cast_last_play_idxs
        with _cast_lock:
            _cast_devices = list(devices)
            _cast_last_play_idxs = []
        out = []
        for i, c in enumerate(_cast_devices):
            info = c.cast_info
            out.append(
                {
                    "index": i,
                    "name": info.friendly_name or "?",
                    "model": info.model_name or "",
                    "uuid": str(info.uuid),
                }
            )
        try:
            stream_port = _ensure_stream_server()
        except Exception:
            stream_port = get_cast_server_port() if is_cast_server_running() else 0
        return jsonify({"ok": True, "devices": out, "lan_ip": get_lan_ip(), "stream_port": stream_port})

    @app.post("/api/chromecast/prepare_search_streams")
    def api_cc_prepare_search_streams():
        data = request.get_json(force=True, silent=True) or {}
        raw = data.get("urls") or []
        labels_raw = data.get("labels") or []
        clean: list[str] = []
        labels_out: list[str] = []
        for i, u in enumerate(raw):
            s = str(u).strip()
            if not s:
                continue
            cu = youtube_url_for_single_video_download(s)
            if not cu:
                continue
            clean.append(cu)
            lbl = ""
            if isinstance(labels_raw, list) and i < len(labels_raw):
                lbl = str(labels_raw[i] or "").strip()
            labels_out.append(lbl or cu[:120])
        if not clean:
            return _json_error("No valid URLs to cast", 400)
        try:
            port = _ensure_stream_server()
        except Exception as e:
            return _json_error(str(e), 500)
        try:
            prewarm_remote_stream_extractions(clean)
        except Exception as ex:
            _log.debug("prewarm search streams for cast: %s", ex)
        ip = get_lan_ip()
        prepared = []
        for u, lab in zip(clean, labels_out):
            cast_u = f"http://{ip}:{port}/remote_stream?u={quote(u, safe='')}"
            prepared.append({"cast_stream_url": cast_u, "label": lab})
        return jsonify({"ok": True, "prepared": prepared})

    @app.post("/api/chromecast/cast_stream_queue")
    def api_cc_cast_stream_queue():
        global _cast_last_play_idxs
        data = request.get_json(force=True, silent=True) or {}
        items_in = data.get("items") or []
        try:
            port = _ensure_stream_server()
        except Exception as e:
            return _json_error(str(e), 500)
        ip = get_lan_ip()
        validated: list[dict[str, str]] = []
        for it in items_in:
            if not isinstance(it, dict):
                continue
            url = str(it.get("cast_stream_url") or "").strip()
            if not validate_chromecast_remote_stream_url(url, lan_ip=ip, server_port=port):
                return _json_error("Invalid stream URL in queue", 400)
            validated.append(
                {"cast_stream_url": url, "label": str(it.get("label") or "")[:240]}
            )
        if not validated:
            return _json_error("No items", 400)
        with _cast_lock:
            devs = list(_cast_devices)
        idxs = _cc_indices_from_request(data, devs)
        if not idxs:
            return _json_error("Tick one or more Chromecasts, or cast once to remember devices.", 422)
        targets = [devs[i] for i in idxs]
        try:
            if len(targets) == 1:
                play_stream_queue_on_cast(targets[0], validated)
            else:
                play_stream_queue_on_casts(targets, validated)
        except Exception as e:
            return _json_error(str(e), 500)
        _cast_last_play_idxs = list(idxs)
        return jsonify({"ok": True, "count": len(validated), "devices": len(targets)})

    @app.post("/api/chromecast/cast_file")
    def api_cc_cast_file():
        global _cast_last_play_idxs
        data = request.get_json(force=True, silent=True) or {}
        cast_stream_url = str(data.get("cast_stream_url") or "").strip()
        media_token = str(data.get("media_token") or "").strip()
        try:
            port = _ensure_stream_server()
        except Exception as e:
            return _json_error(str(e), 500)
        ip = get_lan_ip()
        with _cast_lock:
            devs = list(_cast_devices)
        idxs = _cc_indices_from_request(data, devs)
        if not idxs:
            return _json_error("Tick one or more Chromecasts, or pass device_index / device_indices.", 422)
        targets = [devs[i] for i in idxs]

        if cast_stream_url:
            if not validate_chromecast_remote_stream_url(cast_stream_url, lan_ip=ip, server_port=port):
                return _json_error("Invalid stream cast URL", 400)
            title = str(data.get("stream_title") or "").strip() or None
            try:
                from pychromecast.controllers.media import STREAM_TYPE_BUFFERED

                if len(targets) == 1:
                    play_url(
                        targets[0],
                        cast_stream_url,
                        "video/mp4",
                        stream_type=STREAM_TYPE_BUFFERED,
                        title=title,
                    )
                else:
                    play_url_to_casts(
                        targets,
                        cast_stream_url,
                        "video/mp4",
                        stream_type=STREAM_TYPE_BUFFERED,
                        title=title,
                    )
            except Exception as e:
                return _json_error(str(e), 500)
            _cast_last_play_idxs = list(idxs)
            return jsonify({"ok": True, "url": cast_stream_url, "mime": "video/mp4", "devices": len(targets)})

        if media_token:
            if ".." in media_token or media_token.startswith("/"):
                return _json_error("Invalid token", 400)
            token = media_token
        else:
            abs_raw = str(data.get("abs_path") or "").strip()
            if abs_raw:
                p = Path(abs_raw).expanduser()
                try:
                    p = p.resolve()
                except OSError:
                    pass
                if not _path_allowed_for_library(p):
                    return _json_error("File not in library roots", 403)
            else:
                rel = str(data.get("path") or "").strip()
                p = _safe_under_downloads(rel)
                if p is None or not p.is_file():
                    return _json_error("File not found", 404)
            if not p.is_file():
                return _json_error("File not found", 404)
            token = register_media_path(p.resolve())
        url = f"http://{ip}:{port}/media/{quote(token, safe='/')}"
        name = token.rsplit("/", 1)[-1] if token else "media"
        mime = guess_mime_for_cast(name)
        try:
            if len(targets) == 1:
                play_url(targets[0], url, mime)
            else:
                play_url_to_casts(targets, url, mime)
        except Exception as e:
            return _json_error(str(e), 500)
        _cast_last_play_idxs = list(idxs)
        return jsonify({"ok": True, "url": url, "mime": mime, "devices": len(targets)})

    @app.post("/api/chromecast/play_pause")
    def api_cc_play_pause():
        data = request.get_json(force=True, silent=True) or {}
        with _cast_lock:
            devs = list(_cast_devices)
        idxs = _cc_indices_from_request(data, devs)
        if not idxs:
            return _json_error("Select device(s) or start casting first.", 422)
        prog = media_progress(devs[idxs[0]])
        state = (prog[2] if prog else "") or ""
        try:
            if state == "PAUSED":
                for i in idxs:
                    cast_play_receiver(devs[i])
            else:
                for i in idxs:
                    cast_pause(devs[i])
        except Exception as e:
            return _json_error(str(e), 500)
        return jsonify({"ok": True})

    @app.post("/api/chromecast/seek")
    def api_cc_seek():
        data = request.get_json(force=True, silent=True) or {}
        pos = float(data.get("position_sec", 0))
        with _cast_lock:
            devs = list(_cast_devices)
        idxs = _cc_indices_from_request(data, devs)
        if not idxs:
            return _json_error("Select device(s) or start casting first.", 422)
        try:
            for i in idxs:
                seek_media(devs[i], pos)
        except Exception as e:
            return _json_error(str(e), 500)
        return jsonify({"ok": True})

    @app.post("/api/chromecast/volume")
    def api_cc_volume():
        data = request.get_json(force=True, silent=True) or {}
        v = float(data.get("level", 0.5))
        with _cast_lock:
            devs = list(_cast_devices)
        idxs = _cc_indices_from_request(data, devs)
        if not idxs:
            return _json_error("Select device(s) or start casting first.", 422)
        try:
            for i in idxs:
                set_receiver_volume(devs[i], v)
        except Exception as e:
            return _json_error(str(e), 500)
        return jsonify({"ok": True})

    @app.post("/api/chromecast/repeat")
    def api_cc_repeat():
        global _cast_repeat_cycle
        data = request.get_json(force=True, silent=True) or {}
        _cast_repeat_cycle = (_cast_repeat_cycle + 1) % 3
        modes = ("REPEAT_OFF", "REPEAT_ALL", "REPEAT_SINGLE")
        labels = ("off", "all", "one")
        mode = modes[_cast_repeat_cycle]
        with _cast_lock:
            devs = list(_cast_devices)
        idxs = _cc_indices_from_request(data, devs)
        if not idxs:
            return _json_error("Select device(s) or start casting first.", 422)
        try:
            for i in idxs:
                queue_set_repeat_mode(devs[i], mode)
        except Exception as e:
            return _json_error(str(e), 500)
        return jsonify({"ok": True, "repeat": labels[_cast_repeat_cycle], "mode": mode})

    @app.post("/api/chromecast/shuffle")
    def api_cc_shuffle():
        data = request.get_json(force=True, silent=True) or {}
        on = bool(data.get("shuffle", False))
        with _cast_lock:
            devs = list(_cast_devices)
        idxs = _cc_indices_from_request(data, devs)
        if not idxs:
            return _json_error("Select device(s) or start casting first.", 422)
        try:
            for i in idxs:
                queue_set_shuffle(devs[i], on)
        except Exception as e:
            return _json_error(str(e), 500)
        return jsonify({"ok": True, "shuffle": on})

    @app.post("/api/chromecast/progress")
    def api_cc_progress():
        data = request.get_json(force=True, silent=True) or {}
        with _cast_lock:
            devs = list(_cast_devices)
        idxs = _cc_indices_from_request(data, devs)
        if not idxs:
            return jsonify({"ok": True, "current": 0.0, "duration": None, "state": ""})
        prog = media_progress(devs[idxs[0]])
        if not prog:
            return jsonify({"ok": True, "current": 0.0, "duration": None, "state": ""})
        cur, dur, state = prog
        return jsonify(
            {"ok": True, "current": cur, "duration": dur, "state": state, "paused": state == "PAUSED"}
        )

    @app.post("/api/chromecast/stop_last")
    def api_cc_stop_last():
        ok, msg = stop_last_cast()
        return jsonify({"ok": ok, "message": msg})

    @app.post("/api/chromecast/stop_projection")
    def api_cc_stop_proj():
        data = request.get_json(force=True, silent=True) or {}
        with _cast_lock:
            devs = list(_cast_devices)
        idxs = _cc_indices_from_request(data, devs)
        if not idxs:
            return _json_error("Select device(s) or start casting first.", 422)
        last_err: str | None = None
        for i in idxs:
            try:
                stop_projection(devs[i])
            except Exception as e:
                last_err = str(e)
        if last_err:
            return _json_error(last_err, 500)
        return jsonify({"ok": True})

    @app.get("/api/ytdlp")
    def api_ytdlp():
        from dlpulse_next.ytdlp_update import fetch_pypi_latest_ytdlp_version, get_installed_ytdlp_version

        return jsonify(
            {
                "ok": True,
                "installed": get_installed_ytdlp_version(),
                "pypi_latest": fetch_pypi_latest_ytdlp_version(),
            }
        )

    @app.post("/api/ytdlp/upgrade")
    def api_ytdlp_upgrade():
        from dlpulse_next.ytdlp_update import pip_upgrade_ytdlp, reload_ytdlp_module

        ok, tail = pip_upgrade_ytdlp()
        ver = reload_ytdlp_module() if ok else None
        return jsonify({"ok": ok, "log_tail": tail, "version": ver})

    @app.get("/api/github_update")
    def api_github():
        from dlpulse_next.github_update import check_app_github_update

        info = check_app_github_update()
        dismissed_key = get_app_update_dismissed_key()
        dismiss_key = info.dismiss_key or (info.remote_main_sha or "")[:40] or None
        legacy_sha = get_github_update_dismissed_main_sha()
        dismissed = dismissed_key == dismiss_key if dismiss_key else False
        if not dismissed and legacy_sha and info.kind == "commit":
            dismissed = legacy_sha == (info.remote_main_sha or "")[:40]
        show = info.show_banner and not dismissed
        from dlpulse_next.github_update import get_build_release_tag

        return jsonify(
            {
                "ok": True,
                "show_banner": show,
                "message": info.message,
                "kind": info.kind,
                "release_tag": get_build_release_tag(),
                "installed_version": info.installed_version,
                "latest_version": info.latest_version,
                "latest_tag": info.latest_tag,
                "releases_url": info.releases_url,
                "release_page_url": info.release_page_url,
                "remote_main_sha": info.remote_main_sha,
                "dismiss_key": dismiss_key,
            }
        )

    @app.post("/api/github_update/dismiss")
    def api_github_dismiss():
        data = request.get_json(force=True, silent=True) or {}
        key = str(data.get("dismiss_key") or data.get("sha") or "").strip()
        if key:
            set_app_update_dismissed_key(key)
            if len(key) >= 7 and all(c in "0123456789abcdef" for c in key[:40].lower()):
                set_github_update_dismissed_main_sha(key)
        return jsonify({"ok": True})

    return app


def run_desktop() -> None:
    import webbrowser

    from werkzeug.serving import make_server

    from dlpulse_next.packaged_runtime import is_frozen, show_fatal_error
    from dlpulse_next.settings_store import get_ui_launch_mode

    atexit.register(terminate_external_players)

    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)
    bump_app_launch_count()
    if sys.platform == "linux":
        from dlpulse_next.linux_packaged import apply_packaged_defaults

        apply_packaged_defaults()

    app = create_app()
    srv = make_server("127.0.0.1", 0, app, threaded=True)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True, name="dlpulse-ui").start()
    url = f"http://127.0.0.1:{port}/"
    _log.info("DLPulse Next UI at %s", url)
    from dlpulse_next.branding import window_icon_path

    icon = window_icon_path()
    start_kw = {"icon": icon} if icon else {}

    def _run_browser_only(*, reason: str | None = None) -> None:
        if reason:
            _log.info("Opening UI in browser (%s): %s", reason, url)
        else:
            _log.info("Opening UI in browser (Settings): %s", url)
        webbrowser.open(url)
        if sys.platform == "win32" or is_frozen():
            if reason and get_ui_launch_mode() == "native":
                log_dir = (
                    "%LOCALAPPDATA%\\DLPulseNext\\logs"
                    if sys.platform == "win32"
                    else "~/.local/state/dlpulse-next/logs"
                )
                show_fatal_error(
                    "DLPulse Next",
                    "The native window could not start.\n\n"
                    f"Reason: {reason}\n\n"
                    f"Opened in your default browser:\n{url}\n\n"
                    "Reinstall the latest DLPulse Next installer from GitHub (it bundles\n"
                    "WebView2 and .NET Desktop Runtime).\n"
                    "You can choose “Web page” in Settings → Interface for future launches.\n"
                    "Before reinstalling, close this dialog and end DLPulseNext.exe in Task Manager.\n"
                    f"Log files: {log_dir}",
                )
            threading.Event().wait()
            return
        print(
            "\n  DLPulse Next — UI in your browser.\n"
            f"  {url}\n"
            + (
                f"  (Native window failed: {reason})\n"
                if reason
                else "  (Launch mode: web page — change in Settings → Interface.)\n"
            )
            + "\n  Press Enter here to stop the server (or close this terminal with Ctrl+C).\n",
            flush=True,
        )
        try:
            input("  … ")
        except EOFError:
            threading.Event().wait()

    try:
        launch_mode = get_ui_launch_mode()
        if launch_mode == "browser":
            _run_browser_only()
            return

        import webview
        from webview.errors import WebViewException

        if sys.platform == "win32":
            try:
                from dlpulse_next.windows_bundled_runtimes import apply_bundled_windows_runtimes
                from dlpulse_next.windows_pythonnet import ensure_pythonnet_ready

                apply_bundled_windows_runtimes()
                ensure_pythonnet_ready()
            except RuntimeError as ex:
                _run_browser_only(reason=str(ex))
                return

        webview.create_window("DLPulse", url, width=1680, height=1020, resizable=True)
        try:
            webview.start(**start_kw)
        except (WebViewException, ImportError, OSError, RuntimeError) as ex:
            _run_browser_only(reason=str(ex))
        except Exception as ex:
            if sys.platform == "win32" or is_frozen():
                _run_browser_only(reason=str(ex))
            raise
    finally:
        from dlpulse_next.process_win import terminate_child_processes

        terminate_child_processes()
        terminate_external_players()
        try:
            srv.shutdown()
        except Exception:
            pass
        try:
            stop_cast_server()
        except Exception:
            pass


if __name__ == "__main__":
    run_desktop()
