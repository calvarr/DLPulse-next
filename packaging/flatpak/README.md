# Flatpak (Linux)

Experimental **Flatpak** packaging for DLPulse Next. Uses the GNOME runtime
(GTK3 + WebKit2GTK + GStreamer). Install from source remains the primary path;
see [README — Linux](../../README.md#linux).

## Prerequisites

```bash
flatpak install flathub org.gnome.Platform//49 org.gnome.Sdk//49
```

If `49` is unavailable, list runtimes and adjust `runtime-version` in the manifest:

```bash
flatpak remote-ls flathub --columns=application,version | grep org.gnome.Platform
```

## Build and install (local checkout)

From the repo root:

```bash
bash packaging/flatpak/build.sh
flatpak run com.github.calvarr.DLPulseNext
```

Or manually:

```bash
flatpak-builder --user --install --force-clean build-flatpak \
  packaging/flatpak/com.github.calvarr.DLPulseNext.yml
```

## Files

| File | Role |
|------|------|
| `com.github.calvarr.DLPulseNext.yml` | Manifest (Python app + aria2 module) |
| `com.github.calvarr.DLPulseNext.desktop` | Launcher |
| `com.github.calvarr.DLPulseNext.metainfo.xml` | AppStream metadata (Flathub) |
| `build.sh` | Convenience wrapper |

## Notes

- **ffmpeg** comes from the `imageio-ffmpeg` pip dependency (downloaded on first use).
- **aria2** is built into the Flatpak for parallel downloads.
- **mpv** (external player) is not bundled; use in-app playback or install mpv on the
  host and allow spawning via Flatpak permissions if needed.
- Config and library paths use `~/.config/dlpulse-next` (same as from-source install).

## Flathub submission

For Flathub, replace the `dir` source in the manifest with a pinned git tag archive
and open a PR at [github.com/flathub/flathub](https://github.com/flathub/flathub).
