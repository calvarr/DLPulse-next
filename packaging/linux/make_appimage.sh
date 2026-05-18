#!/usr/bin/env bash
# Build AppImage from PyInstaller onedir: dist/DLPulseNext/
# Native window uses system GTK3 + WebKit2GTK (see README — not bundled).
# Usage: bash packaging/linux/make_appimage.sh [repo_root]
set -euo pipefail
ROOT="$(cd "${1:-.}" && pwd)"
cd "$ROOT"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BUNDLE="dist/DLPulseNext"
if [[ ! -d "$BUNDLE" ]] || [[ ! -x "$BUNDLE/DLPulseNext" ]]; then
  echo "Missing $BUNDLE/DLPulseNext — run PyInstaller first." >&2
  exit 1
fi

APPDIR="build/DLPulseNext.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp -a "$BUNDLE"/. "$APPDIR/usr/bin/"
chmod +x "$APPDIR/usr/bin/DLPulseNext"
bash "$SCRIPT_DIR/strip_internal_gtk.sh" "$APPDIR/usr/bin/_internal"

ICON_SRC="dlpulse_next/static/dlpulse_icon.png"
if [[ -f "$ICON_SRC" ]]; then
  cp -f "$ICON_SRC" "$APPDIR/dlpulse_next.png"
fi

{
  echo "[Desktop Entry]"
  echo "Version=1.0"
  echo "Type=Application"
  echo "Name=DLPulse Next"
  echo "Comment=Media downloader with Chromecast support"
  echo "Exec=AppRun %F"
  [[ -f "$APPDIR/dlpulse_next.png" ]] && echo "Icon=dlpulse_next"
  echo "Categories=Network;AudioVideo;Utility;"
  echo "Terminal=false"
} > "$APPDIR/dlpulse_next.desktop"

cat > "$APPDIR/AppRun" <<'EOS'
#!/bin/sh
if [ -n "${APPDIR:-}" ]; then
  HERE="$APPDIR"
else
  SELF="$(readlink -f "$0" 2>/dev/null || echo "$0")"
  HERE="$(cd "$(dirname "$SELF")" && pwd)"
  case "$HERE" in
    */usr/bin) HERE="$(cd "$HERE/../.." && pwd)" ;;
  esac
fi
BIN="$HERE/usr/bin/DLPulseNext"

export PATH="$HERE/usr/bin:${PATH:-}"
export LANG="${LANG:-en_US.UTF-8}"
export LC_ALL="${LC_ALL:-${LANG:-en_US.UTF-8}}"

# GObject introspection + GLib stack from the host (not bundled).
_gir=""
for _p in /usr/lib/girepository-1.0 /usr/lib64/girepository-1.0; do
  [ -d "$_p" ] && _gir="${_gir:+"$_gir:"}$_p"
done
[ -n "$_gir" ] && export GI_TYPELIB_PATH="$_gir"
export LD_LIBRARY_PATH="/usr/lib:/usr/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# GStreamer: do not scan PyInstaller's _internal for plugins (Python .so files).
_gst=""
for _p in /usr/lib/gstreamer-1.0 /usr/lib64/gstreamer-1.0 /usr/lib/x86_64-linux-gnu/gstreamer-1.0; do
  [ -d "$_p" ] && _gst="${_gst:+"$_gst:"}$_p"
done
[ -n "$_gst" ] && export GST_PLUGIN_PATH="$_gst"

exec "$BIN" "$@"
EOS
chmod +x "$APPDIR/AppRun"

mkdir -p build
OUT="build/DLPulseNext-x86_64.AppImage"
rm -f "$OUT"

if ! command -v appimagetool >/dev/null 2>&1; then
  echo "appimagetool is not on PATH." >&2
  exit 1
fi

export ARCH=x86_64
if appimagetool --help 2>&1 | grep -q no-appstream; then
  appimagetool --no-appstream "$APPDIR" "$OUT"
else
  appimagetool "$APPDIR" "$OUT"
fi
echo "AppImage: $(realpath "$OUT" 2>/dev/null || echo "$OUT")"
