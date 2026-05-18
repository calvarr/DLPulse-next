# Bundled binaries (optional)

PyInstaller picks up **`aria2c`** (or **`aria2c.exe`** on Windows) from this folder when present.

## CI / release builds

GitHub Actions installs aria2 per OS and copies the executable here before `pyinstaller` runs.

## Local build (Linux example)

```bash
sudo pacman -S aria2   # or apt install aria2
mkdir -p packaging/binaries
cp "$(command -v aria2c)" packaging/binaries/aria2c
chmod +x packaging/binaries/aria2c
pyinstaller packaging/pyinstaller/dlpulse_next.spec
```

aria2 is **cross-platform** (Windows, macOS, Linux). Unlike ffmpeg, there is no standard pip wheel; the app bundles a copy when you stage it here, same as a manual sidecar binary next to the app.
