# Linux dependencies (AppImage)

The AppImage bundles **yt-dlp**, **ffmpeg**, **aria2c**, and the Python UI only.

Everything else comes from your distribution.

## Required (native window)

| Component | Arch / Manjaro | Debian / Ubuntu 24.04+ |
|-----------|----------------|-------------------------|
| GTK 3 | `gtk3` | `libgtk-3-0` |
| WebKitGTK | `webkit2gtk-4.1` | `libwebkit2gtk-4.1-0`, `gir1.2-webkit2-4.1` |
| GObject Introspection | `gobject-introspection-runtime` | `gobject-introspection` |

Without these, the app opens in your default browser instead of a native window.

## Recommended (library playback)

**Option A — external player (default on AppImage when GStreamer is missing)**

| Tool | Arch | Debian / Ubuntu |
|------|------|-----------------|
| mpv | `mpv` | `mpv` |

Set **Settings → Default UI mode → External player**, or leave the automatic default.

**Option B — in-app `<video>` player (WebKit + GStreamer)**

| Component | Arch | Debian / Ubuntu |
|-----------|------|-----------------|
| GStreamer | `gstreamer` | `gstreamer1.0-tools` |
| Base plugins | `gst-plugins-base` | `gstreamer1.0-plugins-base` |
| Good plugins | `gst-plugins-good` | `gstreamer1.0-plugins-good` |

Verify: `gst-inspect-1.0 autoaudiosink`

## Check your system

```bash
bash packaging/linux/check-deps.sh
```

## Why not bundle WebKit/GStreamer?

Bundling Ubuntu WebKit/GStreamer into the AppImage breaks on Arch, Fedora, and rolling distros (EGL, `libmount`, GStreamer registry, sandbox). Using the host stack matches how Chrome/Firefox are packaged on Linux and is the only practical way to support many distributions with one build.
