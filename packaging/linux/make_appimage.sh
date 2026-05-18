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
# GTK/WebKit stack only — never override host libc/pthread (causes stack smashing).
export LD_LIBRARY_PATH="$ULIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
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
# WebKit/EGL: prefer bundled stack; avoid DMA-BUF issues in sandboxed GPU paths.
export WEBKIT_DISABLE_DMABUF_RENDERER=1
export WEBKIT_DISABLE_COMPOSITING_MODE=1

# WebKit hardcodes /usr/lib/x86_64-linux-gnu/webkit2gtk-4.0 for helper processes.
WK_SYS="/usr/lib/x86_64-linux-gnu/webkit2gtk-4.0"
WK_BUNDLE="$ULIB/webkit2gtk-4.0"
if [ -x "$WK_BUNDLE/WebKitWebProcess" ] && [ ! -x "$WK_SYS/WebKitWebProcess" ] && command -v bwrap >/dev/null 2>&1; then
  BWRAP=(bwrap --unshare-user-try --die-with-parent --share-net)
  BWRAP+=(--ro-bind "$HERE" "$HERE")
  BWRAP+=(--proc /proc)
  BWRAP+=(--dev-bind /dev /dev)
  BWRAP+=(--bind /tmp /tmp)
  BWRAP+=(--bind /run /run)
  [ -d "$HOME" ] && BWRAP+=(--bind "$HOME" "$HOME")
  [ -d /dev/dri ] && BWRAP+=(--dev-bind /dev/dri /dev/dri)
  for _d in /lib /lib64; do
    [ -d "$_d" ] && BWRAP+=(--ro-bind "$_d" "$_d")
  done
  # Hide distro WebKit/GI (e.g. Arch 4.1) but expose core runtime + helper path.
  BWRAP+=(--tmpfs /usr/lib)
  BWRAP+=(--dir /usr/lib/x86_64-linux-gnu)
  BWRAP+=(--ro-bind "$WK_BUNDLE" "$WK_SYS")
  for _lib in \
    ld-linux-x86-64.so.2 libc.so.6 libm.so.6 libdl.so.2 libpthread.so.0 librt.so.1 \
    libresolv.so.2 libutil.so.1 libz.so.1 libgcc_s.so.1 libstdc++.so.6 libnsl.so.1
  do
    [ -f "/usr/lib/$_lib" ] && BWRAP+=(--ro-bind "/usr/lib/$_lib" "/usr/lib/$_lib")
  done
  [ -f /etc/resolv.conf ] && BWRAP+=(--ro-bind /etc/resolv.conf /etc/resolv.conf)
  [ -d /etc/ssl ] && BWRAP+=(--ro-bind /etc/ssl /etc/ssl)
  [ -f /etc/localtime ] && BWRAP+=(--ro-bind /etc/localtime /etc/localtime)
  [ -d /etc/fonts ] && BWRAP+=(--ro-bind /etc/fonts /etc/fonts)
  [ -d /usr/share/fonts ] && BWRAP+=(--ro-bind /usr/share/fonts /usr/share/fonts)
  [ -d /usr/share/X11 ] && BWRAP+=(--ro-bind /usr/share/X11 /usr/share/X11)
  [ -d /usr/share/icons ] && BWRAP+=(--ro-bind /usr/share/icons /usr/share/icons)
  [ -d /usr/share/glvnd ] && BWRAP+=(--ro-bind /usr/share/glvnd /usr/share/glvnd)
  [ -d /usr/lib/dri ] && BWRAP+=(--ro-bind /usr/lib/dri /usr/lib/dri)
  [ -d /usr/lib/glvnd ] && BWRAP+=(--ro-bind /usr/lib/glvnd /usr/lib/glvnd)
  [ -d /usr/lib64/dri ] && BWRAP+=(--ro-bind /usr/lib64/dri /usr/lib64/dri)
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
