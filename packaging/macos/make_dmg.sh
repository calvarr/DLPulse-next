#!/usr/bin/env bash
# Build .app + DMG from PyInstaller onedir: dist/DLPulseNext/
# Usage: bash packaging/macos/make_dmg.sh [repo_root]
# Env:
#   DMG_ARCH   Override architecture suffix (x86_64 | arm64). Defaults to `uname -m`.
#   MIN_MACOS  LSMinimumSystemVersion for Info.plist (defaults: 10.13 on x86_64, 11.0 on arm64).
set -euo pipefail
ROOT="$(cd "${1:-.}" && pwd)"
cd "$ROOT"

BUNDLE="dist/DLPulseNext"
if [[ ! -d "$BUNDLE" ]] || [[ ! -f "$BUNDLE/DLPulseNext" ]]; then
  echo "Missing PyInstaller bundle at $BUNDLE/DLPulseNext" >&2
  exit 1
fi

ARCH="${DMG_ARCH:-$(uname -m)}"
case "$ARCH" in
  x86_64|amd64) ARCH="x86_64"; DEFAULT_MIN_MACOS="10.13" ;;
  arm64|aarch64) ARCH="arm64"; DEFAULT_MIN_MACOS="11.0" ;;
  *) echo "Unsupported arch: $ARCH" >&2; exit 1 ;;
esac
MIN_MACOS="${MIN_MACOS:-$DEFAULT_MIN_MACOS}"

APP="build/DLPulseNext.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources" "$APP/Contents/Frameworks"

# PyInstaller's macOS launcher hardcodes Python lookup at Contents/Frameworks/Python
# (relative to Contents/MacOS/<launcher>). Wrapping the onedir output flat into
# Contents/MacOS/ produces a broken bundle that fails with "Failed to load Python
# shared library .../Contents/Frameworks/Python" and "ModuleNotFoundError: encodings".
# Correct mac .app layout: launcher in MacOS/, all support files in Frameworks/.
if [[ ! -d "$BUNDLE/_internal" ]]; then
  echo "Missing $BUNDLE/_internal — PyInstaller layout changed?" >&2
  exit 1
fi
cp -a "$BUNDLE/DLPulseNext" "$APP/Contents/MacOS/DLPulseNext"
cp -a "$BUNDLE/_internal"/. "$APP/Contents/Frameworks/"
chmod +x "$APP/Contents/MacOS/DLPulseNext"

# Re-apply ad-hoc signature to the launcher only (deep --sign chokes on
# *.dist-info dirs that codesign mistakes for nested bundles).
codesign --force --sign - "$APP/Contents/MacOS/DLPulseNext" 2>/dev/null || true

# aria2 1.37 (Homebrew build) calls OSSL_PROVIDER_load("legacy") at startup,
# which fails with "OSSL_PROVIDER_load 'legacy' failed" on machines without
# Homebrew because libcrypto.3.dylib hardcodes
# /usr/local/Cellar/openssl@3/<ver>/lib/ossl-modules as MODULESDIR. The CI
# step "Stage aria2c for bundle (macOS)" copies legacy.dylib into
# packaging/binaries/ossl-modules/, the spec file ships it as ossl-modules/
# inside the PyInstaller _internal/, so it ends up at
# Contents/Frameworks/ossl-modules/legacy.dylib here. Patch its libcrypto
# install_name to be relative, and replace the aria2c binary with a tiny
# wrapper that exports OPENSSL_MODULES before exec'ing the real binary.
LEGACY="$APP/Contents/Frameworks/ossl-modules/legacy.dylib"
ARIA="$APP/Contents/Frameworks/aria2c"
if [[ -f "$LEGACY" ]] && [[ -f "$ARIA" ]]; then
  echo "Patching aria2c OpenSSL legacy provider..."
  CUR_LIBCRYPTO=$(otool -L "$LEGACY" | awk '/libcrypto/ {print $1; exit}')
  if [[ -n "$CUR_LIBCRYPTO" ]] && [[ "$CUR_LIBCRYPTO" != "@loader_path/../libcrypto.3.dylib" ]]; then
    install_name_tool -change "$CUR_LIBCRYPTO" \
      "@loader_path/../libcrypto.3.dylib" "$LEGACY"
  fi
  if [[ ! -f "$APP/Contents/Frameworks/aria2c.real" ]]; then
    mv "$ARIA" "$APP/Contents/Frameworks/aria2c.real"
  fi
  cat > "$ARIA" <<'WRAP'
#!/bin/bash
HERE="$(cd "$(dirname "$0")" && pwd)"
export OPENSSL_MODULES="$HERE/ossl-modules"
exec "$HERE/aria2c.real" "$@"
WRAP
  chmod +x "$ARIA"
  codesign --force --sign - "$LEGACY" 2>/dev/null || true
  codesign --force --sign - "$APP/Contents/Frameworks/aria2c.real" 2>/dev/null || true
  echo "  aria2c -> wrapper, real binary -> aria2c.real, legacy provider patched"
fi

# yt-dlp expects ffmpeg/ffprobe with standard names (imageio ships ffmpeg-* only).
PY="${PYTHON:-python3}"
BIN_DIR="$APP/Contents/Resources/bin"
mkdir -p "$BIN_DIR"
FFMPEG_EXE="$("$PY" -c "import imageio_ffmpeg as _i; print(_i.get_ffmpeg_exe())")"
if [[ ! -f "$FFMPEG_EXE" ]]; then
  echo "imageio_ffmpeg did not resolve ffmpeg (PYTHON=$PY)" >&2
  exit 1
fi
cp -f "$FFMPEG_EXE" "$BIN_DIR/ffmpeg"
chmod +x "$BIN_DIR/ffmpeg" || true
IO_DIR="$(dirname "$FFMPEG_EXE")"
if [[ -f "$IO_DIR/ffprobe" ]]; then
  cp -f "$IO_DIR/ffprobe" "$BIN_DIR/ffprobe"
  chmod +x "$BIN_DIR/ffprobe" || true
elif command -v ffprobe &>/dev/null; then
  cp -f "$(command -v ffprobe)" "$BIN_DIR/ffprobe"
  chmod +x "$BIN_DIR/ffprobe" || true
fi
echo "Bundled ffmpeg into $BIN_DIR/ffmpeg"

ICON="dlpulse_next/static/dlpulse_icon.png"
if [[ -f "$ICON" ]]; then
  cp -f "$ICON" "$APP/Contents/Resources/dlpulse_icon.png"
fi

cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>DLPulseNext</string>
  <key>CFBundleIconFile</key>
  <string>dlpulse_icon</string>
  <key>CFBundleIdentifier</key>
  <string>com.calvarr.dlpulse-next</string>
  <key>CFBundleName</key>
  <string>DLPulse Next</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>LSMinimumSystemVersion</key>
  <string>${MIN_MACOS}</string>
</dict>
</plist>
EOF

OUT="build/DLPulseNext-${ARCH}.dmg"
mkdir -p build
rm -f "$OUT"
hdiutil create -volname "DLPulse Next (${ARCH})" -srcfolder "$APP" -ov -format UDZO "$OUT"
echo "DMG: $(pwd)/$OUT (arch=${ARCH}, min macOS=${MIN_MACOS})"
