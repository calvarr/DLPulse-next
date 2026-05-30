# Linux dependencies

DLPulse Next on Linux is installed **from source** (`pip install -e ".[webview-gtk]"`).
The app uses your distro's GTK3, WebKit2GTK, and GStreamer at runtime.

## Required

| Component | Purpose |
|-----------|---------|
| Python 3.11+ | Runtime |
| pip, venv | Install |
| GTK 3 | Native window |
| WebKit2GTK 4.0 or 4.1 | Embedded browser (pywebview) |
| PyGObject (`python-gobject`, `gir1.2-*`) | GTK / WebKit bindings |

## Recommended

| Component | Purpose |
|-----------|---------|
| GStreamer (`gstreamer`, `plugins-base`, `plugins-good`) | In-app library playback (`<video>`) |
| mpv | External player (Settings → External player) |
| ffmpeg | Heavy mux/remux (also available via pip / imageio-ffmpeg) |
| aria2 | Parallel downloads (Settings) |

## Check installation

```bash
bash packaging/linux/check-deps.sh
```

## Per-distro commands

See the main [README.md](../../README.md#linux) for copy-paste install blocks
(Arch, Debian/Ubuntu, Fedora, openSUSE).
