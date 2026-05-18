#!/usr/bin/env bash
# Build .app + DMG from PyInstaller onedir: dist/DLPulseNext/
# Usage: bash packaging/macos/make_dmg.sh [repo_root]
set -euo pipefail
ROOT="$(cd "${1:-.}" && pwd)"
cd "$ROOT"

BUNDLE="dist/DLPulseNext"
if [[ ! -d "$BUNDLE" ]] || [[ ! -f "$BUNDLE/DLPulseNext" ]]; then
  echo "Missing PyInstaller bundle at $BUNDLE/DLPulseNext" >&2
  exit 1
fi

APP="build/DLPulseNext.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp -a "$BUNDLE"/. "$APP/Contents/MacOS/"
chmod +x "$APP/Contents/MacOS/DLPulseNext"

ICON="dlpulse_next/static/dlpulse_icon.png"
if [[ -f "$ICON" ]]; then
  cp -f "$ICON" "$APP/Contents/Resources/dlpulse_icon.png"
fi

cat > "$APP/Contents/Info.plist" <<'EOF'
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
</dict>
</plist>
EOF

OUT="build/DLPulseNext.dmg"
mkdir -p build
rm -f "$OUT"
hdiutil create -volname "DLPulse Next" -srcfolder "$APP" -ov -format UDZO "$OUT"
echo "DMG: $(pwd)/$OUT"
