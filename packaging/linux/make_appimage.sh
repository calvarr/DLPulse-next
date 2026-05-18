#!/usr/bin/env bash
# Build AppImage from PyInstaller onedir: dist/DLPulseNext/
# Usage: bash packaging/linux/make_appimage.sh [repo_root]
set -euo pipefail
ROOT="$(cd "${1:-.}" && pwd)"
cd "$ROOT"

BUNDLE="dist/DLPulseNext"
if [[ ! -d "$BUNDLE" ]]; then
  echo "Missing $BUNDLE — run PyInstaller first." >&2
  exit 1
fi
if [[ ! -f "$BUNDLE/DLPulseNext" ]]; then
  echo "Missing $BUNDLE/DLPulseNext executable." >&2
  exit 1
fi

if ! command -v appimagetool &>/dev/null; then
  echo "appimagetool is not on PATH." >&2
  exit 1
fi

APPDIR="build/DLPulseNext.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp -a "$BUNDLE"/. "$APPDIR/usr/bin/"
chmod +x "$APPDIR/usr/bin/DLPulseNext"

ICON_SRC="dlpulse_next/static/dlpulse_icon.png"
if [[ -f "$ICON_SRC" ]]; then
  cp -f "$ICON_SRC" "$APPDIR/dlpulse_next.png"
fi

cat > "$APPDIR/AppRun" <<'EOS'
#!/bin/sh
SELF="$0"
while [ -L "$SELF" ]; do
  DIR="$(dirname "$SELF")"
  SELF="$(readlink "$SELF")"
  [ "${SELF#/}" = "$SELF" ] && SELF="$DIR/$SELF"
done
HERE="$(cd "$(dirname "$SELF")" && pwd)"
export PATH="$HERE/usr/bin:${PATH:-}"
cd "$HERE/usr/bin" || exit 1
exec "./DLPulseNext" "$@"
EOS
chmod +x "$APPDIR/AppRun"

{
  echo "[Desktop Entry]"
  echo "Version=1.0"
  echo "Type=Application"
  echo "Name=DLPulse Next"
  echo "Comment=Media downloader with Chromecast support"
  echo "Exec=DLPulseNext %u"
  [[ -f "$APPDIR/dlpulse_next.png" ]] && echo "Icon=dlpulse_next"
  echo "Categories=Network;AudioVideo;Utility;"
  echo "Terminal=false"
} > "$APPDIR/dlpulse_next.desktop"

mkdir -p build
OUT="build/DLPulseNext-x86_64.AppImage"
rm -f "$OUT"
export ARCH=x86_64
if appimagetool --help 2>&1 | grep -q no-appstream; then
  appimagetool --no-appstream "$APPDIR" "$OUT"
else
  appimagetool "$APPDIR" "$OUT"
fi
echo "AppImage: $(realpath "$OUT" 2>/dev/null || echo "$OUT")"
