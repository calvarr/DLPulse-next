# Packaging (DLPulse Next)

After PyInstaller produces `dist/DLPulseNext/`:

| Platform | Script | Output |
|----------|--------|--------|
| Linux | — | Install from source (see README); AppImage script is unmaintained |
| Windows | `packaging/windows/build_installer.ps1` | `build/DLPulseNext-Setup.exe` (needs [NSIS](https://nsis.sourceforge.io/)) |
| macOS | `packaging/macos/make_dmg.sh` | `build/DLPulseNext.dmg` |

GitHub Actions runs these automatically (see `.github/workflows/build.yml`).

**Version label in app:** continuous builds embed only `build_commit.txt` (short SHA in UI). Tagged releases (`v*`) also write `build_version.txt` — shown in header and Settings.
