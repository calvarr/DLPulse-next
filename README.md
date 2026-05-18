# DLPulse Next

Desktop rebuild of [DLPulse](https://github.com/calvarr/DLPulse) **without Flet / flet-video**: a **native window** ([pywebview](https://pywebview.flowrl.com/)) loads a local **Flask** UI. Playback uses the **HTML5 `<video>`** element with the same **local HTTP relay** (`/remote_stream`) as the original app, plus **mpv/VLC** as an optional external player. **Chromecast**, **yt-dlp** format presets, **YouTube + SoundCloud search**, **playlists**, and **library** behaviour are ported from `flet_app/`.

## Run (development)

```bash
cd /home/investigatii/Desktop/yt/dlpulse_next
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m dlpulse_next
```

Or: `.venv/bin/dlpulse-next`

You can also run the UI module as a file (after `pip install -e .`, so dependencies are in the venv):

```bash
cd /home/investigatii/Desktop/yt/dlpulse_next
.venv/bin/python dlpulse_next/webapp.py
```

Do **not** use a different copy of the tree without installing; `import dlpulse_next` needs the project root on `PYTHONPATH`, which `-m dlpulse_next` and `webapp.py` (bootstrap) set up for you.

## Linux: native window (pywebview + GTK)

Pywebview on Linux uses **GTK + WebKit** (imports `gi`, WebKitGTK) or **Qt** (`qtpy`). If those Python bindings are missing, the app **still starts**: it opens the **same URL in your default browser** and keeps Flask running until you press **Enter** in the terminal.

To get a real desktop window on **Arch / Manjaro**, install system libraries, then PyGObject into the venv:

```bash
sudo pacman -S gtk3 webkit2gtk gobject-introspection-runtime
cd /path/to/dlpulse_next
.venv/bin/pip install -e ".[webview-gtk]"
```

If `pip install PyGObject` fails, install build deps: `sudo pacman -S gcc pkgconf cairo python-cairo` (names vary slightly by distro). See [pywebview installation](https://pywebview.flowrl.com/guide/installation.html).

On **Windows** and **macOS**, the default backends are usually available without extra steps.

## Configuration

Settings are stored under:

- Linux/macOS: `~/.config/dlpulse-next/settings.json`
- Windows: `%APPDATA%\DLPulseNext\settings.json`

Optional **cookies** for yt-dlp: place `cookies.txt` next to the installed `yt_core` module (same idea as the Flet app), or set `YT_COOKIES_FILE`.

## Scope vs old Flet app

- **Player**: no Flutter/media_kit; internal preview is **browser engine video** + existing **cast_http** relay (same yt-dlp + ffmpeg mux paths for DASH). For difficult streams, use **external player** commands in Settings or **Play in browser** for the relay URL.
- **UI**: first iteration covers search, URL probe, playlist rows, downloads with progress, library browse/reveal/play file, Chromecast discover/cast file/stop last, settings, yt-dlp pip upgrade, GitHub “new commits” banner.
- **Not yet ported** in this scaffold: multi-select queue editor parity, every Cast edge case from `main.py`.

## Desktop bundles (GitHub Actions + PyInstaller)

Similar idea to the **Flet** repo: pushing to `main` / `master` or a tag `v*` runs **`.github/workflows/build.yml`**, which builds **Linux / Windows / macOS** zips via **PyInstaller** (`packaging/pyinstaller/dlpulse_next.spec`).

Each bundle includes:

- **yt-dlp** (full Python package + extractors)
- **ffmpeg** via **imageio-ffmpeg** (platform binary next to the app)
- Flask **static** UI, pywebview, Chromecast dependencies

**Linux:** WebKitGTK is still a **system** dependency on the machine where you run the binary (like a dev install); the workflow installs it on the Ubuntu runner for the build only.

**Releases:** tag `v1.0.0` → normal GitHub Release; pushes to the default branch also refresh the prerelease tag **`dlpulse-next-continuous`** (separate from the Flet app’s `continuous` tag if both exist in one org).

Local one-off build: see `packaging/pyinstaller/README.md`.

## Layout

- `dlpulse_next/webapp.py` — Flask API + desktop bootstrap
- `dlpulse_next/static/` — HTML/CSS/JS shell
- `dlpulse_next/yt_core.py`, `cast_http.py`, `chromecast_helper.py`, `ffmpeg_tools.py` — adapted from `../yt/flet_app/`
