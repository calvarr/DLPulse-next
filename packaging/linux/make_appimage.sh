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

GIRDIR="$APPDIR/usr/lib/x86_64-linux-gnu/girepository-1.0"
for _required in cairo-1.0.typelib Gtk-3.0.typelib WebKit2-4.0.typelib; do
  if [[ ! -f "$GIRDIR/$_required" ]]; then
    echo "make_appimage: missing required typelib $_required in AppDir." >&2
    exit 1
  fi
done
WK_INJ="$APPDIR/usr/lib/x86_64-linux-gnu/webkit2gtk-4.0/injected-bundle/libwebkit2gtkinjectedbundle.so"
if [[ ! -f "$WK_INJ" ]]; then
  echo "make_appimage: missing WebKit injected bundle at $WK_INJ" >&2
  exit 1
fi

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
export LANG="${LANG:-en_US.UTF-8}"
export LC_ALL="${LC_ALL:-${LANG:-en_US.UTF-8}}"
# Bundled GTK/WebKit; host GPU/EGL/Mesa (bundled Ubuntu GL breaks on Arch/Manjaro).
export LD_LIBRARY_PATH="$ULIB:/usr/lib:/usr/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export GI_TYPELIB_PATH="$ULIB/girepository-1.0"
export GSETTINGS_SCHEMA_DIR="$HERE/usr/share/glib-2.0/schemas"
export XDG_DATA_DIRS="$HERE/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
if [ -f "$HERE/etc/fonts/fonts.conf" ]; then
  export FONTCONFIG_PATH="$HERE/etc/fonts"
  export FONTCONFIG_FILE="$HERE/etc/fonts/fonts.conf"
fi
if [ -f "$ULIB/gdk-pixbuf-2.0/loaders.cache" ]; then
  export GDK_PIXBUF_MODULE_FILE="$ULIB/gdk-pixbuf-2.0/loaders.cache"
fi
export WEBKIT_DISABLE_DMABUF_RENDERER=1
export WEBKIT_DISABLE_COMPOSITING_MODE=1
# Bundled Ubuntu Wayland EGL breaks on X11 (Arch/Manjaro); use host Mesa via X11 backend.
case "${XDG_SESSION_TYPE:-}" in
  wayland) ;;
  *) export GDK_BACKEND=x11 ;;
esac
# Optional: DLPULSE_GL_SOFTWARE=1 forces llvmpipe if GPU init still fails.
if [ "${DLPULSE_GL_SOFTWARE:-}" = 1 ]; then
  export LIBGL_ALWAYS_SOFTWARE=1
  export MESA_LOADER_DRIVER_OVERRIDE=llvmpipe
fi

# WebKit/GStreamer must not scan PyInstaller's _internal for plugins (Python .so files).
_gst=""
for _p in /usr/lib/gstreamer-1.0 /usr/lib64/gstreamer-1.0 /usr/lib/x86_64-linux-gnu/gstreamer-1.0; do
  [ -d "$_p" ] && _gst="${_gst:+"$_gst:"}$_p"
done
[ -n "$_gst" ] && export GST_PLUGIN_PATH="$_gst"

# libwebkit is patched at build time to /tmp/dlpulse-wk/webkit2gtk-4.0 (Ubuntu path missing on Arch).
WK_BUNDLE="$ULIB/webkit2gtk-4.0"
if [ -d "$WK_BUNDLE" ]; then
  mkdir -p /tmp/dlpulse-wk
  ln -sfn "$WK_BUNDLE" /tmp/dlpulse-wk/webkit2gtk-4.0
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
