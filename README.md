# DLPulse Next

Cross-platform desktop app for downloading and playing media with **yt-dlp** — YouTube & SoundCloud search, local library, built-in player, Chromecast, format presets. Native window via [pywebview](https://pywebview.flowrl.com/) + Flask UI.

Part of the [DLPulse](https://calvarr.github.io/) ecosystem. Desktop rebuild **without Flet** — playback uses HTML5 `<video>` and the same local HTTP relay as the original app.

## Install (pre-built)

Download the latest builds from **[GitHub Releases](https://github.com/calvarr/DLPulse-next/releases)**.

| Channel | Link | When to use |
|---------|------|-------------|
| **Continuous** (latest `main`) | [dlpulse-next-continuous](https://github.com/calvarr/DLPulse-next/releases/tag/dlpulse-next-continuous) | Bleeding edge; app header shows Git commit |
| **Stable** (tagged) | [All releases](https://github.com/calvarr/DLPulse-next/releases) | Versioned builds (`v2.0.0`, …); header shows release tag |

Each bundle includes **yt-dlp**, **ffmpeg**, **aria2c**, **WebKitGTK/GTK** (Linux AppImage), and the full UI.

### Linux — AppImage

1. Download **`DLPulseNext-x86_64.AppImage`** from the [continuous release](https://github.com/calvarr/DLPulse-next/releases/tag/dlpulse-next-continuous) (or a stable tag).
2. Make it executable and run:

```bash
chmod +x DLPulseNext-x86_64.AppImage
./DLPulseNext-x86_64.AppImage
```

**Native window:** WebKitGTK and GTK3 are **bundled inside the AppImage** — no separate install needed on most distros. If the native window still fails, the app opens in your default browser.

For **development from source**, install WebKitGTK on your system:

```bash
# Arch / Manjaro
sudo pacman -S gtk3 webkit2gtk gobject-introspection-runtime

# Debian / Ubuntu
sudo apt install libgtk-3-0 libwebkit2gtk-4.1-0 gir1.2-webkit2-4.1
```

Optional: integrate with your desktop (AppImageLauncher, or move the file to `~/Applications` / `/opt` and add a `.desktop` entry).

### Windows — installer

1. Download **`DLPulseNext-Setup.exe`** from [Releases](https://github.com/calvarr/DLPulse-next/releases/tag/dlpulse-next-continuous).
2. Run the installer (installs under `Program Files\DLPulse Next`).
3. Launch **DLPulse Next** from the Start menu or desktop shortcut.

To uninstall: **Settings → Apps** or **Add/Remove Programs**, or run `uninstall.exe` in the install folder.

### macOS — DMG

1. Download **`DLPulseNext.dmg`** from [Releases](https://github.com/calvarr/DLPulse-next/releases/tag/dlpulse-next-continuous).
2. Open the DMG and drag **DLPulse Next** to **Applications**.
3. On first launch, if macOS blocks the app: **System Settings → Privacy & Security → Open Anyway** (unsigned build from CI).

## Configuration

Settings are stored under:

- Linux/macOS: `~/.config/dlpulse-next/settings.json`
- Windows: `%APPDATA%\DLPulseNext\settings.json`

Optional **cookies** for yt-dlp: place `cookies.txt` next to the bundled app data, or set `YT_COOKIES_FILE`.

## Run from source (development)

```bash
git clone https://github.com/calvarr/DLPulse-next.git
cd DLPulse-next
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m dlpulse_next
```

Or: `.venv/bin/dlpulse-next`

**Linux dev — native window:** install GTK/WebKit system packages, then:

```bash
.venv/bin/pip install -e ".[webview-gtk]"
```

See [pywebview installation](https://pywebview.flowrl.com/guide/installation.html).

## Build installers locally

After `pip install -e ".[build]"` and PyInstaller (`packaging/pyinstaller/dlpulse_next.spec`):

| Platform | Script | Output |
|----------|--------|--------|
| Linux | `bash packaging/linux/make_appimage.sh` | `build/DLPulseNext-x86_64.AppImage` |
| Windows | `pwsh packaging/windows/build_installer.ps1` | `build/DLPulseNext-Setup.exe` (needs [NSIS](https://nsis.sourceforge.io/)) |
| macOS | `bash packaging/macos/make_dmg.sh` | `build/DLPulseNext.dmg` |

CI builds all three on push to `main` and on tags `v*` — see `.github/workflows/build.yml`.

## Project layout

- `dlpulse_next/webapp.py` — Flask API + desktop bootstrap
- `dlpulse_next/static/` — HTML/CSS/JS shell
- `dlpulse_next/yt_core.py`, `cast_http.py`, `chromecast_helper.py`, `ffmpeg_tools.py` — core logic

## License

MIT — see [LICENSE](LICENSE).
