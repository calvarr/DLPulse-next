#!/usr/bin/env bash
# Build AppImage from PyInstaller onedir: dist/DLPulseNext/
#
# Thin AppImage — relies on host GTK3 + WebKit2GTK + GStreamer (see README).
# Bundling those would break on rolling distros (Arch/Fedora) because of
# GLib/GIO sandbox/registry mismatches.
#
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
  mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
  cp -f "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/256x256/apps/dlpulse_next.png"
fi

cat > "$APPDIR/dlpulse_next.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=DLPulse Next
Comment=Media downloader with Chromecast support
Exec=AppRun %F
Icon=dlpulse_next
Categories=Network;AudioVideo;Utility;
Terminal=false
EOF

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

# WebKitWebProcess needs host GStreamer plugins; sandbox blocks /usr/lib/gstreamer-1.0.
export WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1

# Use host GObject introspection + GLib (not bundled).
_gir=""
for _p in /usr/lib/girepository-1.0 /usr/lib64/girepository-1.0 /usr/lib/x86_64-linux-gnu/girepository-1.0; do
  [ -d "$_p" ] && _gir="${_gir:+"$_gir:"}$_p"
done
[ -n "$_gir" ] && export GI_TYPELIB_PATH="$_gir"
export LD_LIBRARY_PATH="/usr/lib:/usr/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# Host GStreamer plugins only (rthook reorders LD_LIBRARY_PATH after PyInstaller starts).
_gst=""
for _p in /usr/lib/gstreamer-1.0 /usr/lib64/gstreamer-1.0 /usr/lib/x86_64-linux-gnu/gstreamer-1.0; do
  [ -d "$_p" ] && _gst="${_gst:+"$_gst:"}$_p"
done
[ -n "$_gst" ] && export GST_PLUGIN_SYSTEM_PATH="$_gst"
unset GST_PLUGIN_PATH 2>/dev/null || true
for _scan in /usr/libexec/gstreamer-1.0/gst-plugin-scanner /usr/lib/gstreamer-1.0/gst-plugin-scanner /usr/lib/x86_64-linux-gnu/gstreamer-1.0/gst-plugin-scanner; do
  [ -x "$_scan" ] && export GST_PLUGIN_SCANNER="$_scan" && break
done
_gst_cache="${XDG_CACHE_HOME:-$HOME/.cache}/dlpulse-next"
if mkdir -p "$_gst_cache" 2>/dev/null; then
  rm -f "$_gst_cache/gstreamer-registry.bin"
  export GST_REGISTRY="$_gst_cache/gstreamer-registry.bin"
fi

exec "$BIN" "$@"
EOS
chmod +x "$APPDIR/AppRun"

mkdir -p build
OUT="build/DLPulseNext-x86_64.AppImage"
rm -f "$OUT"

if ! command -v appimagetool >/dev/null 2>&1; then
  APPIMAGETOOL="$ROOT/build/appimagetool-x86_64.AppImage"
  if [[ ! -x "$APPIMAGETOOL" ]]; then
    echo "Downloading appimagetool..."
    curl -fsSL -o "$APPIMAGETOOL" \
      "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGETOOL"
  fi
  APPIMAGETOOL_CMD=("$APPIMAGETOOL")
else
  APPIMAGETOOL_CMD=(appimagetool)
fi

export ARCH=x86_64
APPIMAGETOOL_ARGS=("$APPDIR" "$OUT")
if "${APPIMAGETOOL_CMD[@]}" --help 2>&1 | grep -q no-appstream; then
  APPIMAGETOOL_ARGS=(--no-appstream "${APPIMAGETOOL_ARGS[@]}")
fi

# CI runners often lack FUSE; --appimage-extract-and-run is the documented fallback.
if ! "${APPIMAGETOOL_CMD[@]}" "${APPIMAGETOOL_ARGS[@]}" 2>/dev/null; then
  "${APPIMAGETOOL_CMD[@]}" --appimage-extract-and-run "${APPIMAGETOOL_ARGS[@]}"
fi

chmod +x "$OUT"
echo "AppImage: $(realpath "$OUT" 2>/dev/null || echo "$OUT")"
