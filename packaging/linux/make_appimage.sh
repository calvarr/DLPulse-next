#!/usr/bin/env bash
# Build a SELF-CONTAINED AppImage from the PyInstaller onedir dist/DLPulseNext/.
#
# Unlike the old "thin" AppImage, this bundles the entire GTK3 + WebKit2GTK +
# GStreamer stack and their transitive dependencies, so the app runs on any
# modern Linux without the user installing webkit2gtk/gtk3/gstreamer.
#
# Portability model (standard AppImage): we DO bundle the GUI stack, but we do
# NOT bundle glibc or the GL/driver stack — those must come from the host. The
# AppImage therefore runs on hosts whose glibc is >= the build host's glibc.
# Build on the oldest distro you want to support (CI uses Ubuntu 22.04).
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
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib"
cp -a "$BUNDLE"/. "$APPDIR/usr/bin/"
chmod +x "$APPDIR/usr/bin/DLPulseNext"

LIBDIR="$APPDIR/usr/lib"

# ---------------------------------------------------------------------------
# Host layout detection (multiarch on Debian/Ubuntu, flat on Arch/Fedora).
# ---------------------------------------------------------------------------
MULTIARCH="$(gcc -print-multiarch 2>/dev/null || true)"
[[ -z "$MULTIARCH" ]] && MULTIARCH="x86_64-linux-gnu"

SEARCH_DIRS=()
for d in \
  "/usr/lib/$MULTIARCH" "/usr/lib64" "/usr/lib" \
  "/lib/$MULTIARCH" "/lib64" "/lib" \
  "/usr/local/lib/$MULTIARCH" "/usr/local/lib"; do
  [[ -d "$d" ]] && SEARCH_DIRS+=("$d")
done

host_libdir() {
  # First search dir that actually exists; used as the canonical host libdir.
  for d in "/usr/lib/$MULTIARCH" "/usr/lib64" "/usr/lib"; do
    [[ -d "$d" ]] && { echo "$d"; return; }
  done
  echo "/usr/lib"
}
HOSTLIB="$(host_libdir)"

find_lib() {
  local name="$1" d
  for d in "${SEARCH_DIRS[@]}"; do
    if [[ -e "$d/$name" ]]; then
      echo "$d/$name"
      return 0
    fi
  done
  return 1
}

# ---------------------------------------------------------------------------
# Exclude list: libraries that MUST come from the host (never bundle).
# glibc family (must match host kernel/loader) and the GL/driver stack
# (tied to the host GPU driver). Mirrors the AppImage pkg2appimage excludelist.
# ---------------------------------------------------------------------------
is_excluded() {
  case "$1" in
    ld-linux*|libc.so.*|libm.so.*|libdl.so.*|libpthread.so.*|librt.so.*|\
    libresolv.so.*|libutil.so.*|libnsl.so.*|libnss_*|libthread_db*|libanl.so.*|\
    libmvec.so.*|libBrokenLocale.so.*|\
    libGL.so.*|libGLX.so.*|libGLdispatch.so.*|libOpenGL.so.*|libGLU.so.*|\
    libEGL.so.*|libGLESv2.so.*|libGLESv1_CM.so.*|\
    libgbm.so.*|libdrm.so.*|libdrm_*|libvulkan.so.*|\
    libva.so.*|libva-drm.so.*|libva-x11.so.*|libva-glx.so.*|libvdpau.so.*|\
    libselinux.so.*|libudev.so.*|libsystemd.so.*)
      return 0 ;;
  esac
  return 1
}

SEEN="$(mktemp)"
trap 'rm -f "$SEEN"' EXIT

# Copy a shared object (or executable) plus its non-excluded transitive deps.
bundle_with_deps() {
  local src="$1"
  [[ -e "$src" ]] || return 0
  local base; base="$(basename "$src")"
  if ! grep -qxF "$base" "$SEEN"; then
    echo "$base" >> "$SEEN"
    if [[ ! -e "$LIBDIR/$base" ]]; then
      cp -L "$src" "$LIBDIR/$base"
    fi
  fi
  # Recurse over ldd-resolved dependencies.
  local line dep
  while IFS= read -r line; do
    dep="$(awk '/=>/ {print $3} !/=>/ && /^\// {print $1}' <<<"$line")"
    [[ -z "$dep" || ! -e "$dep" ]] && continue
    local dbase; dbase="$(basename "$dep")"
    is_excluded "$dbase" && continue
    grep -qxF "$dbase" "$SEEN" && continue
    echo "$dbase" >> "$SEEN"
    [[ ! -e "$LIBDIR/$dbase" ]] && cp -L "$dep" "$LIBDIR/$dbase"
    bundle_with_deps "$dep"
  done < <(ldd "$src" 2>/dev/null | tr -d '\t')
}

# ---------------------------------------------------------------------------
# Detect WebKit2GTK / libsoup version (4.1 + soup3, else 4.0 + soup2).
# ---------------------------------------------------------------------------
WK_VER="" SOUP_VER=""
if find_lib "libwebkit2gtk-4.1.so.0" >/dev/null; then
  WK_VER="4.1"; SOUP_VER="3.0"
elif find_lib "libwebkit2gtk-4.0.so.37" >/dev/null; then
  WK_VER="4.0"; SOUP_VER="2.4"
else
  echo "ERROR: libwebkit2gtk (4.0/4.1) not found on host — install webkit2gtk dev." >&2
  exit 1
fi
echo "WebKit2GTK $WK_VER + libsoup $SOUP_VER"

# ---------------------------------------------------------------------------
# Bundle the core GUI/media libraries (deps follow via ldd recursion).
# ---------------------------------------------------------------------------
CORE_LIBS=(
  "libgtk-3.so.0" "libgdk-3.so.0" "libgdk_pixbuf-2.0.so.0"
  "libwebkit2gtk-${WK_VER}.so.0" "libwebkit2gtk-${WK_VER}.so.37"
  "libjavascriptcoregtk-${WK_VER}.so.0" "libjavascriptcoregtk-${WK_VER}.so.18"
  "libsoup-${SOUP_VER}.so.0" "libsoup-2.4.so.1" "libsoup-3.0.so.0"
  "libgstreamer-1.0.so.0" "libgstapp-1.0.so.0" "libgstaudio-1.0.so.0"
  "libgstvideo-1.0.so.0" "libgstpbutils-1.0.so.0" "libgsttag-1.0.so.0"
  "librsvg-2.so.2"
  "libpulse.so.0" "libpulse-mainloop-glib.so.0" "libasound.so.2"
  "libpangocairo-1.0.so.0" "libpango-1.0.so.0" "libpangoft2-1.0.so.0"
)
for lib in "${CORE_LIBS[@]}"; do
  p="$(find_lib "$lib" 2>/dev/null || true)"
  [[ -n "$p" ]] && bundle_with_deps "$p"
done

# Make versioned soname symlinks resolvable (some libs are dlopened by base name).
( cd "$LIBDIR"
  for so in lib*.so.*; do
    [[ -e "$so" ]] || continue
    base="${so%.so.*}.so"
    [[ -e "$base" ]] || ln -sf "$so" "$base" 2>/dev/null || true
  done )

# ---------------------------------------------------------------------------
# WebKit helper processes + injected bundle (separate executables).
# ---------------------------------------------------------------------------
WK_LIBEXEC="$APPDIR/usr/lib/webkit2gtk-${WK_VER}"
mkdir -p "$WK_LIBEXEC"
WK_HELPER_SRC=""
for d in \
  "$HOSTLIB/webkit2gtk-${WK_VER}" \
  "/usr/libexec/webkit2gtk-${WK_VER}" \
  "/usr/lib/webkit2gtk-${WK_VER}"; do
  if [[ -d "$d" ]]; then WK_HELPER_SRC="$d"; break; fi
done
if [[ -n "$WK_HELPER_SRC" ]]; then
  for f in WebKitWebProcess WebKitNetworkProcess MiniBrowser; do
    [[ -f "$WK_HELPER_SRC/$f" ]] && { cp -L "$WK_HELPER_SRC/$f" "$WK_LIBEXEC/"; bundle_with_deps "$WK_HELPER_SRC/$f"; }
  done
  if [[ -d "$WK_HELPER_SRC/injected-bundle" ]]; then
    mkdir -p "$WK_LIBEXEC/injected-bundle"
    cp -aL "$WK_HELPER_SRC/injected-bundle/." "$WK_LIBEXEC/injected-bundle/"
    for so in "$WK_LIBEXEC/injected-bundle"/*.so*; do
      [[ -e "$so" ]] && bundle_with_deps "$so"
    done
  fi
  echo "Bundled WebKit helpers from $WK_HELPER_SRC"
else
  echo "WARN: WebKit helper process dir not found; web view may fail." >&2
fi

# ---------------------------------------------------------------------------
# GObject-introspection typelibs (override PyInstaller's with host versions).
# ---------------------------------------------------------------------------
GI_DST="$APPDIR/usr/lib/girepository-1.0"
mkdir -p "$GI_DST"
for d in \
  "$HOSTLIB/girepository-1.0" \
  "/usr/lib/girepository-1.0" \
  "/usr/lib64/girepository-1.0"; do
  [[ -d "$d" ]] && cp -an "$d/." "$GI_DST/" 2>/dev/null || true
done

# ---------------------------------------------------------------------------
# GIO modules (TLS via glib-networking, proxy resolver).
# ---------------------------------------------------------------------------
GIO_DST="$APPDIR/usr/lib/gio/modules"
mkdir -p "$GIO_DST"
for d in \
  "$HOSTLIB/gio/modules" \
  "/usr/lib/gio/modules" "/usr/lib64/gio/modules"; do
  if [[ -d "$d" ]]; then
    for so in "$d"/*.so; do
      [[ -e "$so" ]] || continue
      cp -L "$so" "$GIO_DST/"
      bundle_with_deps "$so"
    done
  fi
done

# ---------------------------------------------------------------------------
# GdkPixbuf loaders + cache (paths made relative to GDK_PIXBUF_MODULEDIR).
# ---------------------------------------------------------------------------
PIXBUF_DST="$APPDIR/usr/lib/gdk-pixbuf-2.0/2.10.0/loaders"
mkdir -p "$PIXBUF_DST"
PIXBUF_SRC=""
for d in \
  "$HOSTLIB/gdk-pixbuf-2.0/2.10.0/loaders" \
  "/usr/lib/gdk-pixbuf-2.0/2.10.0/loaders" \
  "/usr/lib64/gdk-pixbuf-2.0/2.10.0/loaders"; do
  [[ -d "$d" ]] && { PIXBUF_SRC="$d"; break; }
done
if [[ -n "$PIXBUF_SRC" ]]; then
  for so in "$PIXBUF_SRC"/*.so; do
    [[ -e "$so" ]] || continue
    cp -L "$so" "$PIXBUF_DST/"
    bundle_with_deps "$so"
  done
  QUERY_LOADERS=""
  for c in gdk-pixbuf-query-loaders gdk-pixbuf-query-loaders-64; do
    command -v "$c" >/dev/null 2>&1 && { QUERY_LOADERS="$c"; break; }
  done
  if [[ -n "$QUERY_LOADERS" ]]; then
    ( cd "$PIXBUF_DST" && "$QUERY_LOADERS" ./*.so ) > "$PIXBUF_DST/../loaders.cache" 2>/dev/null || true
    # Strip absolute build paths so entries resolve via GDK_PIXBUF_MODULEDIR.
    sed -i "s|\"$PIXBUF_DST/|\"|g; s|\"$PWD/$PIXBUF_DST/|\"|g" "$PIXBUF_DST/../loaders.cache" 2>/dev/null || true
    sed -i 's|"\./|"|g' "$PIXBUF_DST/../loaders.cache" 2>/dev/null || true
  fi
fi

# ---------------------------------------------------------------------------
# GStreamer plugins + scanner (for in-app <video>).
# ---------------------------------------------------------------------------
GST_DST="$APPDIR/usr/lib/gstreamer-1.0"
mkdir -p "$GST_DST"
GST_SRC=""
for d in \
  "$HOSTLIB/gstreamer-1.0" \
  "/usr/lib/gstreamer-1.0" "/usr/lib64/gstreamer-1.0"; do
  [[ -d "$d" ]] && { GST_SRC="$d"; break; }
done
if [[ -n "$GST_SRC" ]]; then
  for so in "$GST_SRC"/libgst*.so; do
    [[ -e "$so" ]] || continue
    cp -L "$so" "$GST_DST/"
    bundle_with_deps "$so"
  done
  echo "Bundled $(ls "$GST_DST"/libgst*.so 2>/dev/null | wc -l) GStreamer plugins"
fi
# gst-plugin-scanner
for d in \
  "$HOSTLIB/gstreamer1.0/gstreamer-1.0" \
  "/usr/libexec/gstreamer-1.0" \
  "$GST_SRC"; do
  if [[ -f "$d/gst-plugin-scanner" ]]; then
    cp -L "$d/gst-plugin-scanner" "$GST_DST/gst-plugin-scanner"
    bundle_with_deps "$d/gst-plugin-scanner"
    break
  fi
done

# ---------------------------------------------------------------------------
# GSettings schemas (GTK/WebKit read org.gtk.* settings).
# ---------------------------------------------------------------------------
SCHEMA_DST="$APPDIR/usr/share/glib-2.0/schemas"
mkdir -p "$SCHEMA_DST"
if [[ -f "/usr/share/glib-2.0/schemas/gschemas.compiled" ]]; then
  cp -f "/usr/share/glib-2.0/schemas/gschemas.compiled" "$SCHEMA_DST/"
elif command -v glib-compile-schemas >/dev/null 2>&1 && [[ -d "/usr/share/glib-2.0/schemas" ]]; then
  cp -f /usr/share/glib-2.0/schemas/*.xml "$SCHEMA_DST/" 2>/dev/null || true
  glib-compile-schemas "$SCHEMA_DST" >/dev/null 2>&1 || true
fi

# Icon theme (avoid missing-icon warnings / broken buttons).
for theme in hicolor Adwaita; do
  if [[ -d "/usr/share/icons/$theme" ]]; then
    mkdir -p "$APPDIR/usr/share/icons/$theme"
    cp -an "/usr/share/icons/$theme/index.theme" "$APPDIR/usr/share/icons/$theme/" 2>/dev/null || true
  fi
done

# ---------------------------------------------------------------------------
# Deduplicate: drop _internal copies of libs we bundled into usr/lib so there
# is a single authoritative version. PyInstaller's binary uses DT_RPATH
# ($ORIGIN/_internal), which is searched BEFORE LD_LIBRARY_PATH — so a stale
# _internal copy would otherwise shadow the bundled usr/lib one (e.g. an older
# libstdc++ breaking WebKit/ICU). Python-only libs (libssl, liblzma, …) that
# we did NOT bundle stay in _internal and are still found there.
# ---------------------------------------------------------------------------
INTERNAL="$APPDIR/usr/bin/_internal"
if [[ -d "$INTERNAL" ]]; then
  dedup=0
  for so in "$LIBDIR"/lib*.so*; do
    [[ -e "$so" ]] || continue
    b="$(basename "$so")"
    if [[ -e "$INTERNAL/$b" || -L "$INTERNAL/$b" ]]; then
      rm -f "$INTERNAL/$b"
      dedup=$((dedup + 1))
    fi
  done
  echo "Deduplicated $dedup libs from _internal (usr/lib is authoritative)"
fi

# ---------------------------------------------------------------------------
# App icon + desktop entry.
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# AppRun: point every subsystem at the bundled stack (self-contained).
# ---------------------------------------------------------------------------
cat > "$APPDIR/AppRun" <<EOS
#!/bin/sh
if [ -n "\${APPDIR:-}" ]; then
  HERE="\$APPDIR"
else
  SELF="\$(readlink -f "\$0" 2>/dev/null || echo "\$0")"
  HERE="\$(cd "\$(dirname "\$SELF")" && pwd)"
fi
export APPDIR="\$HERE"

# Tell the PyInstaller runtime hooks this is the self-contained bundle so they
# do NOT reorder library paths toward the host (which would defeat bundling).
export DLPULSE_SELFCONTAINED=1

# Pin the exact WebKit/Soup versions that were bundled so gobject-introspection
# does not pick a different host typelib (which would load host WebKit + libs).
export DLPULSE_WEBKIT_VER="${WK_VER}"
export DLPULSE_SOUP_VER="${SOUP_VER}"

WK_VER="${WK_VER}"

export PATH="\$HERE/usr/bin:\${PATH:-}"
export LANG="\${LANG:-en_US.UTF-8}"
export LC_ALL="\${LC_ALL:-\${LANG:-en_US.UTF-8}}"

# Bundled libraries first (then PyInstaller _internal, then any host fallback).
export LD_LIBRARY_PATH="\$HERE/usr/lib:\$HERE/usr/bin/_internal:\${LD_LIBRARY_PATH:-}"

# GObject introspection typelibs.
export GI_TYPELIB_PATH="\$HERE/usr/lib/girepository-1.0:\${GI_TYPELIB_PATH:-}"

# GIO modules (TLS / proxy).
export GIO_MODULE_DIR="\$HERE/usr/lib/gio/modules"

# GdkPixbuf loaders.
export GDK_PIXBUF_MODULEDIR="\$HERE/usr/lib/gdk-pixbuf-2.0/2.10.0/loaders"
export GDK_PIXBUF_MODULE_FILE="\$HERE/usr/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache"

# GSettings schemas.
export GSETTINGS_SCHEMA_DIR="\$HERE/usr/share/glib-2.0/schemas"

# Icons / fonts (fonts use host config via fontconfig).
export XDG_DATA_DIRS="\$HERE/usr/share:\${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"

# WebKit: use bundled helper processes + injected bundle; sandbox off (no bwrap).
export WEBKIT_EXEC_PATH="\$HERE/usr/lib/webkit2gtk-\${WK_VER}"
export WEBKIT_INJECTED_BUNDLE_PATH="\$HERE/usr/lib/webkit2gtk-\${WK_VER}/injected-bundle"
export WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1
export WEBKIT_DISABLE_COMPOSITING_MODE=1

# GStreamer: bundled plugins + scanner, writable registry.
export GST_PLUGIN_SYSTEM_PATH="\$HERE/usr/lib/gstreamer-1.0"
export GST_PLUGIN_PATH="\$HERE/usr/lib/gstreamer-1.0"
export GST_PLUGIN_SCANNER="\$HERE/usr/lib/gstreamer-1.0/gst-plugin-scanner"
_gst_cache="\${XDG_CACHE_HOME:-\$HOME/.cache}/dlpulse-next"
if mkdir -p "\$_gst_cache" 2>/dev/null; then
  export GST_REGISTRY="\$_gst_cache/gstreamer-registry.bin"
fi

exec "\$HERE/usr/bin/DLPulseNext" "\$@"
EOS
chmod +x "$APPDIR/AppRun"

# ---------------------------------------------------------------------------
# Pack the AppImage.
# ---------------------------------------------------------------------------
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
echo "Self-contained AppImage: $(realpath "$OUT" 2>/dev/null || echo "$OUT")"
echo "Bundled libs: $(ls "$LIBDIR"/lib*.so* 2>/dev/null | wc -l)"
