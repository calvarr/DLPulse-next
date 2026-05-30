# DLPulse Next

## Legal notice

**DLPulse** is open-source software intended solely for educational purposes, technical research, and managing your personal media library.

1. **Nature of the software** — DLPulse is an automated wrapper around third-party utilities (such as yt-dlp and ffmpeg). The author does not host, distribute, or control copyrighted media. The app interacts only with publicly available internet sources; you are solely responsible for how you use that data.
2. **Your responsibility** — You must comply with copyright laws and each platform’s terms of service. The software is for personal offline/local storage; redistribution or commercial use is your responsibility. It is provided “as is” without warranty; the author is not liable for account blocks or other penalties from third parties.
3. **No affiliation** — DLPulse is not affiliated with or sponsored by any streaming platform. Trademarks belong to their owners.

If you do not agree, do not use, install, or distribute this software. Full text: [LEGAL.md](LEGAL.md).

---

Cross-platform desktop shell for **educational use** and personal media libraries — wraps **yt-dlp** and **ffmpeg** to resolve supported public URLs, manage a local archive, play media, and cast. Keyword/URL search depends on site extractors. Native window via [pywebview](https://pywebview.flowrl.com/) + Flask UI.

Part of the [DLPulse](https://calvarr.github.io/) ecosystem. Desktop rebuild **without Flet** — playback uses HTML5 `<video>` and the same local HTTP relay as the original app.

## Install

### Pre-built installers (Windows & macOS only)

Download from **[GitHub Releases](https://github.com/calvarr/DLPulse-next/releases)**. On **Linux**, install [from source](#linux) (see below).

| Channel | Link |
|---------|------|
| **Continuous** (latest `main`) | [dlpulse-next-continuous](https://github.com/calvarr/DLPulse-next/releases/tag/dlpulse-next-continuous) |
| **Stable** (tagged) | [All releases](https://github.com/calvarr/DLPulse-next/releases) |

| Platform | File | Notes |
|----------|------|--------|
| **Windows** | `DLPulseNext-Setup.exe` | Bundles yt-dlp, ffmpeg, aria2c, WebView2 UI |
| **macOS — Intel** | `DLPulseNext-x86_64.dmg` | For Intel Macs (macOS 10.13+). Bundles yt-dlp, ffmpeg, aria2c, WKWebView UI |
| **macOS — Apple Silicon** | `DLPulseNext-arm64.dmg` | For M1/M2/M3/M4 Macs (macOS 11+). Bundles yt-dlp, ffmpeg, aria2c, WKWebView UI |

> If you double‑click the DMG and macOS says **"not compatible with this Mac"**, you downloaded the wrong architecture. Use `DLPulseNext-x86_64.dmg` on Intel Macs and `DLPulseNext-arm64.dmg` on Apple Silicon. Run `uname -m` in Terminal to check (`x86_64` = Intel, `arm64` = Apple Silicon).

**Windows:** run the installer **as Administrator** (right-click → **Run as administrator**), then launch from the Start menu. The setup **bundles .NET Desktop Runtime 8 (x64)** and **Microsoft Edge WebView2** next to the app under `C:\Program Files\DLPulse Next\` — you do **not** need to install them separately. Installer size is larger (~300–500 MB) because of these runtimes.

**Windows — installer “Error opening file for writing” on `DLPulseNext.exe`?**

1. Close DLPulse Next completely (including any error dialog that opened the browser — the app may still run in the background).
2. Open **Task Manager** → end **DLPulseNext.exe** (and **ffmpeg.exe** if launched from the app folder).
3. Run `DLPulseNext-Setup.exe` again **as Administrator**.
4. If it still fails, uninstall **DLPulse Next** from Settings → Apps, reboot, then install the latest setup from [Releases](https://github.com/calvarr/DLPulse-next/releases).

**Windows — black `ffmpeg` console window stays open?**

Newer builds run ffmpeg without a visible console and stop it when you close the app. If you still see one: close DLPulse Next, end **DLPulseNext.exe** and **ffmpeg.exe** in Task Manager, then update to the latest continuous installer.

**Windows — app does nothing / no window?**

1. Right-click `DLPulseNext-Setup.exe` → **Properties** → if you see **Unblock**, check it and apply (SmartScreen/download block).
2. Install [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/) if missing.
3. Use the **latest** continuous installer (older builds did not bundle runtimes). Manual install is only needed for very old builds: [WebView2](https://developer.microsoft.com/microsoft-edge/webview2/) and [.NET Desktop 8 x64](https://dotnet.microsoft.com/download/dotnet/8.0).
4. Check logs: `%LOCALAPPDATA%\DLPulseNext\logs\startup.log` and `crash.log`.
5. Run from PowerShell for a visible error (debug build from source):  
   `$env:DLPULSE_DEBUG=1; & "${env:ProgramFiles}\DLPulse Next\DLPulseNext.exe"`
6. On Windows the default is **Web page** (your browser). If the native window fails, the app opens the browser and switches to web page for the next launch. In **Settings → Interface** you can choose **Native application** for a desktop window (requires bundled or system .NET Desktop + WebView2).

**macOS — install & first run (step by step)**

> The DMG is **ad-hoc signed** (no Apple Developer ID), so macOS Gatekeeper will block the first launch. This is normal — follow the steps below.

1. **Pick the right DMG for your CPU.**

   Run this in **Terminal** to check which Mac you have:

   ```bash
   uname -m
   ```

   - `x86_64` → download **`DLPulseNext-x86_64.dmg`** (Intel)
   - `arm64`  → download **`DLPulseNext-arm64.dmg`** (Apple Silicon: M1/M2/M3/M4)

   If you pick the wrong one, macOS will say **"not compatible with this Mac"**.

2. **Mount the DMG.** Double‑click `DLPulseNext-<arch>.dmg` in Finder. A new "DLPulse Next" volume appears in the Finder sidebar with `DLPulseNext.app` inside.

3. **Copy the app to Applications.** Drag `DLPulseNext.app` from the mounted volume into your `Applications` folder. Do **not** run it from inside the DMG. After copying, eject the DMG (right‑click the volume → **Eject**).

4. **Bypass Gatekeeper on first launch.** Pick **one** of the methods below. The first one is recommended.

   **Method A — Right‑click → Open (recommended)**

   1. Open `Applications` in Finder.
   2. **Right‑click** (or Control‑click) on `DLPulseNext.app` → **Open**.
   3. macOS shows a dialog: *"DLPulse Next can't be opened because it is from an unidentified developer / Apple cannot check it for malicious software."* Click **Open**.
   4. The app starts and the warning will not appear again on subsequent launches.

   **Method B — System Settings → Privacy & Security**

   1. Try to open the app once by double‑clicking it. macOS will refuse and show a warning dialog. Close that dialog.
   2. Open **System Settings → Privacy & Security**.
   3. Scroll down to the **Security** section. You will see a line like: *"DLPulseNext was blocked from use because it is not from an identified developer."* Click **Open Anyway** next to it. (You may need to enter your password.)
   4. Try to open the app again — confirm in the new dialog that appears.

   **Method C — Strip the quarantine attribute via Terminal (advanced)**

   When macOS quarantines an app, it sets the `com.apple.quarantine` extended attribute on it. Removing it makes macOS treat the app as if it were not downloaded from the internet:

   ```bash
   xattr -dr com.apple.quarantine /Applications/DLPulseNext.app
   ```

   After this, double‑click works normally without any Gatekeeper prompt.

5. **Avoid quarantine altogether (optional).** If you frequently work with unsigned tools, you can prevent macOS from setting the quarantine attribute on files downloaded with Safari:

   ```bash
   defaults write com.apple.LaunchServices LSQuarantine -bool false
   ```

   Set it back to `true` if you want the protection back. This applies only to files downloaded **after** changing the setting.

**macOS — troubleshooting**

| Error | Fix |
|---|---|
| *"not compatible with this Mac"* | Wrong architecture — re‑download the DMG matching `uname -m`. |
| *"is damaged and can't be opened. You should move it to the Trash"* | The quarantine bit is set and the ad-hoc signature is being rejected. Run `xattr -dr com.apple.quarantine /Applications/DLPulseNext.app` (Method C above), then try again. |
| *"can't be opened because Apple cannot check it for malicious software"* | Use Method A or B above. |
| App opens but immediately crashes / no window appears | Check Console.app → search for `DLPulseNext`. The Flask UI also serves on a local port; if you see "Server listening on 127.0.0.1:PORT" in logs, open `http://127.0.0.1:PORT` in your browser. |

---

### Linux

There is **no Linux download** on [Releases](https://github.com/calvarr/DLPulse-next/releases) — only the Windows installer and macOS DMG. **AppImage is no longer shipped.**

Two supported paths on Linux:

| Method | Best for |
|--------|----------|
| **[Flatpak](#flatpak-recommended)** | Desktop use — sandboxed bundle (GTK/WebKit from GNOME runtime) |
| **[From source](#from-source)** | Development, AUR/COPR packaging, or full control over system libs |

Both need a working **GTK3 + WebKit2GTK** stack at runtime (Flatpak gets this from the GNOME runtime; from-source uses your distro packages).

---

#### Flatpak (recommended)

Build and install locally from a git clone (not published on Flathub yet):

```bash
# One-time: Flatpak tools + GNOME runtime
sudo pacman -S flatpak flatpak-builder   # Arch / Manjaro
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install flathub org.gnome.Platform//49 org.gnome.Sdk//49

git clone https://github.com/calvarr/DLPulse-next.git
cd DLPulse-next
bash packaging/flatpak/build.sh
flatpak run com.github.calvarr.DLPulseNext
```

Details: [packaging/flatpak/README.md](packaging/flatpak/README.md)

---

#### From source

**Requirements:** Python **3.11+**, pip, and the system packages below.

##### 1. System dependencies

Pick **one** block for your distribution.

**Arch Linux / Manjaro / EndeavourOS**

```bash
sudo pacman -S --needed \
  python python-pip python-gobject \
  gtk3 webkit2gtk-4.1 gobject-introspection-runtime \
  gstreamer gst-plugins-base gst-plugins-good \
  mpv ffmpeg aria2
```

**Debian 12 / Ubuntu 22.04** (WebKit **4.0**)

```bash
sudo apt update
sudo apt install -y \
  python3 python3-pip python3-venv python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
  libgtk-3-0 libwebkit2gtk-4.0-37 gir1.2-webkit2-4.0 gobject-introspection \
  gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  mpv ffmpeg aria2
```

**Debian 13 / Ubuntu 24.04+** (WebKit **4.1**)

```bash
sudo apt update
sudo apt install -y \
  python3 python3-pip python3-venv python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
  libgtk-3-0 libwebkit2gtk-4.1-0 gir1.2-webkit2-4.1 gobject-introspection \
  gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  mpv ffmpeg aria2
```

**Fedora**

```bash
sudo dnf install -y \
  python3 python3-pip python3-gobject \
  gtk3 webkit2gtk4.1 \
  gstreamer1-plugins-base gstreamer1-plugins-good \
  mpv ffmpeg aria2
```

**openSUSE Tumbleweed / Leap**

```bash
sudo zypper install -y \
  python3 python3-pip python3-gobject \
  gtk3 webkit2gtk3 \
  gstreamer-plugins-base gstreamer-plugins-good \
  mpv ffmpeg aria2
```

| Package role | Why |
|--------------|-----|
| `gtk3`, `webkit2gtk` | Native window (pywebview) |
| `python-gobject` / `gir1.2-*` | GTK/WebKit bindings |
| `gstreamer` + `plugins-base` + `plugins-good` | In-app `<video>` playback |
| `mpv` | External player (Settings → External player) |
| `ffmpeg` | Mux/remux (also bundled via pip if missing) |
| `aria2` | Optional parallel downloads (Settings) |

**Verify (optional):**

```bash
gst-inspect-1.0 autoaudiosink   # should print "Factory Details"
python3 -c "import gi; gi.require_version('WebKit2','4.1'); from gi.repository import WebKit2"
# On Ubuntu 22.04 use WebKit2 4.0 instead of 4.1 in the line above
```

From a git checkout: `bash packaging/linux/check-deps.sh`

##### 2. Install DLPulse Next

```bash
git clone https://github.com/calvarr/DLPulse-next.git
cd DLPulse-next
python3 -m venv .venv
source .venv/bin/activate   # fish: source .venv/bin/activate.fish
pip install -U pip wheel
pip install -e ".[webview-gtk]"
```

##### 3. Run

```bash
dlpulse-next
# or: python -m dlpulse_next
```

**Desktop shortcut (optional):**

```bash
mkdir -p ~/.local/share/applications
cat > ~/.local/share/applications/dlpulse-next.desktop <<EOF
[Desktop Entry]
Type=Application
Name=DLPulse Next
Comment=Media downloader with Chromecast
Exec=$HOME/DLPulse-next/.venv/bin/dlpulse-next
Icon=applications-multimedia
Terminal=false
Categories=AudioVideo;Network;
EOF
# Edit Exec= if you cloned elsewhere
update-desktop-database ~/.local/share/applications 2>/dev/null || true
```

More detail: [packaging/linux/linux-dependencies.md](packaging/linux/linux-dependencies.md)

---

## Configuration

Settings: `~/.config/dlpulse-next/settings.json` (Linux/macOS) or `%APPDATA%\DLPulseNext\settings.json` (Windows). Keys include `ui_launch_mode` (`native` | `browser`), `playback_mode`, download folder, and players.

Optional **cookies** for yt-dlp: `cookies.txt` in the config folder, or set `YT_COOKIES_FILE`.

## Development

Same as Linux install; after `pip install -e ".[webview-gtk]"`:

```bash
.venv/bin/python -m dlpulse_next
```

See [pywebview installation](https://pywebview.flowrl.com/guide/installation.html).

## Build installers locally (Windows / macOS)

```bash
pip install -e ".[build]"
pyinstaller packaging/pyinstaller/dlpulse_next.spec
```

| Platform | Script | Output |
|----------|--------|--------|
| Windows | `pwsh packaging/windows/build_installer.ps1` | `build/DLPulseNext-Setup.exe` |
| macOS | `bash packaging/macos/make_dmg.sh` | `build/DLPulseNext-<arch>.dmg` (where `<arch>` is `x86_64` or `arm64`, auto-detected via `uname -m`; override with `DMG_ARCH=`) |

CI builds the Windows installer and macOS DMG on push to `main` and on tags `v*`. **Linux** is not in CI — use [Flatpak](#flatpak-recommended) or [from source](#from-source).

## Project layout

- `dlpulse_next/webapp.py` — Flask API + desktop bootstrap
- `dlpulse_next/static/` — HTML/CSS/JS shell
- `dlpulse_next/yt_core.py`, `cast_http.py`, `chromecast_helper.py`, `ffmpeg_tools.py` — core logic

## License

MIT — see [LICENSE](LICENSE).
