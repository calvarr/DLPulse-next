#!/usr/bin/env bash
# Build AppImage from PyInstaller onedir: dist/DLPulseNext/
# Bundles GTK3 + WebKit2GTK + PyGObject for pywebview (no system WebKit install needed).
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
  echo "Exec=DLPulseNext %u"
  [[ -f "$APPDIR/dlpulse_next.png" ]] && echo "Icon=dlpulse_next"
  echo "Categories=Network;AudioVideo;Utility;"
  echo "Terminal=false"
} > "$APPDIR/dlpulse_next.desktop"

bash "$SCRIPT_DIR/bundle_gtk_webkit.sh" "$APPDIR" "$APPDIR/usr/bin/DLPulseNext"

LINUXDEPLOY="${LINUXDEPLOY:-}"
if [[ -z "$LINUXDEPLOY" ]] && command -v linuxdeploy >/dev/null 2>&1; then
  LINUXDEPLOY="$(command -v linuxdeploy)"
fi

if [[ -n "$LINUXDEPLOY" ]] && [[ -x "$LINUXDEPLOY" ]]; then
  export APPIMAGE_EXTRACT_AND_RUN=1
  GTK_PLUGIN="${LINUXDEPLOY_GTK_PLUGIN:-}"
  if [[ -z "$GTK_PLUGIN" ]] && command -v linuxdeploy-plugin-gtk >/dev/null 2>&1; then
    GTK_PLUGIN="$(command -v linuxdeploy-plugin-gtk)"
  fi
  DEPLOY_ARGS=(--appdir="$APPDIR" --executable="$APPDIR/usr/bin/DLPulseNext")
  if [[ -f "$APPDIR/dlpulse_next.desktop" ]]; then
    DEPLOY_ARGS+=(--desktop-file="$APPDIR/dlpulse_next.desktop")
  fi
  if [[ -f "$APPDIR/dlpulse_next.png" ]]; then
    DEPLOY_ARGS+=(--icon-file="$APPDIR/dlpulse_next.png")
  fi
  if [[ -n "$GTK_PLUGIN" ]] && [[ -x "$GTK_PLUGIN" ]]; then
    DEPLOY_ARGS+=(--plugin gtk)
    export LINUXDEPLOY_GTK_PLUGIN="$GTK_PLUGIN"
  fi
  "$LINUXDEPLOY" "${DEPLOY_ARGS[@]}" || true
fi

# AppRun last — bundled GTK/WebKit must win over host libraries.
cat > "$APPDIR/AppRun" <<'EOS'
#!/bin/sh
SELF="$0"
while [ -L "$SELF" ]; do
  DIR="$(dirname "$SELF")"
  SELF="$(readlink "$SELF")"
  [ "${SELF#/}" = "$SELF" ] && SELF="$DIR/$SELF"
done
HERE="$(cd "$(dirname "$SELF")" && pwd)"
ULIB="$HERE/usr/lib/x86_64-linux-gnu"
export PATH="$HERE/usr/bin:${PATH:-}"
export LD_LIBRARY_PATH="$ULIB:$HERE/usr/lib:${LD_LIBRARY_PATH:-}"
export GI_TYPELIB_PATH="$ULIB/girepository-1.0"
export GSETTINGS_SCHEMA_DIR="$HERE/usr/share/glib-2.0/schemas"
export XDG_DATA_DIRS="$HERE/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
if [ -f "$ULIB/gdk-pixbuf-2.0/loaders.cache" ]; then
  export GDK_PIXBUF_MODULE_FILE="$ULIB/gdk-pixbuf-2.0/loaders.cache"
fi
cd "$HERE/usr/bin" || exit 1
exec "./DLPulseNext" "$@"
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
