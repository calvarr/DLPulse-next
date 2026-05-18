# PyInstaller bundle (DLPulse Next)

Produces a **onedir** application under `dist/DLPulseNext/` with:

- Flask static UI (`dlpulse_next/static`)
- **yt-dlp** (Python package + extractors)
- **ffmpeg** from **imageio-ffmpeg** (per platform binary)
- **aria2c** when staged under `packaging/binaries/` (optional; see `packaging/binaries/README.md`)
- pywebview, Chromecast stack, etc.

## Local build

```bash
cd /path/to/dlpulse_next
python3 -m venv .venv
.venv/bin/pip install -e ".[build]"
echo "$(git rev-parse HEAD 2>/dev/null || echo unknown)" > dlpulse_next/build_commit.txt
.venv/bin/pyinstaller packaging/pyinstaller/dlpulse_next.spec
```

Run: `dist/DLPulseNext/DLPulseNext` (Linux/macOS) or `dist\DLPulseNext\DLPulseNext.exe` (Windows).

## Linux runtime

GTK + WebKitGTK are still expected on the **target** machine (same as a dev install). The bundle does not ship full WebKit; if bindings are missing, the app falls back to opening the UI in the default browser.

## GitHub Actions

See `.github/workflows/build.yml` in this repository (if this tree lives inside a larger monorepo, copy that workflow to the **repository root** and set `defaults.run.working-directory` to this folder).
