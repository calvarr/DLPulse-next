# Linux dependencies

DLPulse Next on Linux ships as a **thin AppImage** (or `pip install -e .` from
source). Both paths use your distro's GTK / WebKit2GTK / GStreamer at runtime.

## Required

| Component | Purpose |
|-----------|---------|
| GTK 3 | Native window |
| WebKit2GTK 4.0 or 4.1 | Embedded browser (pywebview) |
| PyGObject (`python-gobject`, `gir1.2-*`) | GTK / WebKit bindings (from-source only — bundled inside AppImage) |
| Python 3.11+ | From-source path only (bundled inside AppImage) |

## Recommended

| Component | Purpose |
|-----------|---------|
| GStreamer (`gstreamer`, `plugins-base`, `plugins-good`) | In-app library playback (`<video>`) |
| mpv | External player (Settings → External player) |
| ffmpeg | Heavy mux/remux (pip and AppImage ship a copy via imageio-ffmpeg) |
| aria2 | Parallel downloads (bundled inside AppImage) |

## Check installation

```bash
bash packaging/linux/check-deps.sh
```

## Per-distro commands

See the main [README.md](../../README.md#linux) for copy-paste install blocks
(Arch, Debian/Ubuntu, Fedora, openSUSE).

## Why a thin AppImage?

Bundling WebKit/GStreamer into the AppImage breaks on rolling distros (Arch,
Fedora) because of GLib / GIO sandbox / GStreamer registry mismatches. The thin
AppImage keeps only Python + the app and uses the host's GTK/WebKit/GStreamer —
the same stack the from-source install relies on. This matches how other GTK
apps are distributed and avoids the cross-distro failures we hit before.
