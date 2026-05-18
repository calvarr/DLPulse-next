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

bash "$SCRIPT_DIR/bundle_gtk_webkit.sh" "$APPDIR" "$APPDIR/usr/bin/DLPulseNext"

# AppRun — set bundled GTK/WebKit env; keep PyInstaller ELF at usr/bin/DLPulseNext.
# Do not run linuxdeploy here: it replaces the main binary with a wrapper script.
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
ULIB="$HERE/usr/lib/x86_64-linux-gnu"
BIN="$HERE/usr/bin/DLPulseNext"

export PATH="$HERE/usr/bin:${PATH:-}"
# GTK/WebKit stack only — never override host libc/pthread (causes stack smashing).
export LD_LIBRARY_PATH="$ULIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export GI_TYPELIB_PATH="$ULIB/girepository-1.0"
export GSETTINGS_SCHEMA_DIR="$HERE/usr/share/glib-2.0/schemas"
export XDG_DATA_DIRS="$HERE/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
if [ -f "$ULIB/gdk-pixbuf-2.0/loaders.cache" ]; then
  export GDK_PIXBUF_MODULE_FILE="$ULIB/gdk-pixbuf-2.0/loaders.cache"
fi

# WebKit hardcodes /usr/lib/x86_64-linux-gnu/webkit2gtk-4.0 for helper processes.
WK_SYS="/usr/lib/x86_64-linux-gnu/webkit2gtk-4.0"
WK_BUNDLE="$ULIB/webkit2gtk-4.0"
if [ -x "$WK_BUNDLE/WebKitWebProcess" ] && [ ! -x "$WK_SYS/WebKitWebProcess" ] && command -v bwrap >/dev/null 2>&1; then
  BWRAP=(bwrap --unshare-user-try --die-with-parent --share-net)
  BWRAP+=(--ro-bind "$WK_BUNDLE" "$WK_SYS")
  for _d in /tmp /dev /proc /sys /run; do
    [ -d "$_d" ] && BWRAP+=(--bind "$_d" "$_d")
  done
  [ -d "$HOME" ] && BWRAP+=(--bind "$HOME" "$HOME")
  [ -f /etc/resolv.conf ] && BWRAP+=(--ro-bind /etc/resolv.conf /etc/resolv.conf)
  [ -d /etc/ssl ] && BWRAP+=(--ro-bind /etc/ssl /etc/ssl)
  [ -f /etc/localtime ] && BWRAP+=(--ro-bind /etc/localtime /etc/localtime)
  [ -d /usr/share/fonts ] && BWRAP+=(--ro-bind /usr/share/fonts /usr/share/fonts)
  exec "${BWRAP[@]}" -- "$BIN" "$@"
fi

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
