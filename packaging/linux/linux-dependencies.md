# Linux dependencies

DLPulse Next on Linux is installed **from source** with pip. System packages provide GTK, WebKit, and GStreamer — the same stack as running from a normal Python venv.

## Required

| Component | Purpose |
|-----------|---------|
| Python 3.11+ | Runtime |
| PyGObject (`python-gobject`, `gir1.2-*`) | GTK / WebKit bindings |
| GTK 3 | Native window |
| WebKit2GTK 4.0 or 4.1 | Embedded browser (pywebview) |

## Recommended

| Component | Purpose |
|-----------|---------|
| GStreamer (`gstreamer`, `plugins-base`, `plugins-good`) | In-app library playback (`<video>`) |
| mpv | External player (Settings → External player) |
| ffmpeg | Heavy mux/remux (pip also ships a copy via imageio-ffmpeg) |
| aria2 | Parallel downloads in Settings |

## Check installation

```bash
bash packaging/linux/check-deps.sh
```

## Per-distro commands

See the main [README.md](../../README.md#linux-install-from-source) for copy-paste install blocks (Arch, Debian/Ubuntu, Fedora, openSUSE).

## Why no AppImage?

Bundling WebKit/GStreamer from Ubuntu into an AppImage breaks on Arch, Fedora, and other rolling distros (EGL, GLib, GStreamer registry, sandbox). Installing on the host matches how other GTK apps are distributed and avoids those failures.
