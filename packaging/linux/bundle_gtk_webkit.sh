#!/usr/bin/env bash
# Copy WebKit2GTK helpers, GTK/WebKit shared libs, GIR typelibs into an AppDir.
# Must NOT bundle libc/libpthread/libstdc++ — LD_LIBRARY_PATH would break the loader.
set -euo pipefail

APPDIR="${1:?Usage: bundle_gtk_webkit.sh AppDir}"
EXE="${2:?Usage: bundle_gtk_webkit.sh AppDir path/to/DLPulseNext}"

if [[ ! -d "$APPDIR" ]] || [[ ! -x "$EXE" ]]; then
  echo "bundle_gtk_webkit: invalid AppDir or executable." >&2
  exit 1
fi

ARCH_LIB="$APPDIR/usr/lib/x86_64-linux-gnu"
GIRDIR="$ARCH_LIB/girepository-1.0"
mkdir -p "$ARCH_LIB" "$GIRDIR" "$APPDIR/usr/share/glib-2.0/schemas"

# Never ship core loader/runtime libs — host libc must always win.
NEVER_BUNDLE=(
  ld-linux-x86-64.so.2
  ld-linux.so.2
  libc.so.6
  libm.so.6
  libdl.so.2
  libpthread.so.0
  librt.so.1
  libutil.so.1
  libresolv.so.2
  libnss_files.so.2
  libnss_dns.so.2
  libnsl.so.1
  libstdc++.so.6
  libgcc_s.so.1
  libEGL.so.1
  libGL.so.1
  libGLX.so.0
  libGLdispatch.so.0
  libgbm.so.1
  libdrm.so.2
)

is_blocked() {
  local base="$1"
  local blocked
  for blocked in "${NEVER_BUNDLE[@]}"; do
    [[ "$base" == "$blocked" || "$base" == "$blocked."* ]] && return 0
  done
  # Host display/GPU stack must not be overridden by Ubuntu build libs.
  case "$base" in
    libEGL.so.*|libGL.so.*|libGLX.so.*|libGLdispatch.so.*|libGLESv2.so.*|libgbm.so.*|libdrm.so.* \
    |libX11.so.*|libX11-xcb.so.*|libXau.so.*|libXdmcp.so.*|libXext.so.*|libXfixes.so.* \
    |libXrandr.so.*|libXcursor.so.*|libXdamage.so.*|libXcomposite.so.*|libXinerama.so.* \
    |libXi.so.*|libXrender.so.*|libxcb.so.*|libxcb-*.so.* \
    |libwayland-client.so.*|libwayland-server.so.*|libwayland-cursor.so.*|libwayland-egl.so.*)
      return 0
      ;;
  esac
  return 1
}

# WebKit hardcodes /usr/lib/x86_64-linux-gnu/webkit2gtk-4.0 (Ubuntu). Arch has no such path;
# repoint to /tmp/dlpulse-wk/ (same length, null-padded) and symlink at runtime in AppRun.
patch_webkit_paths() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  python3 - "$file" <<'PY'
import sys
path = sys.argv[1]
with open(path, "rb") as f:
    data = f.read()
old_lib = b"/usr/lib/x86_64-linux-gnu/webkit2gtk-4.0"
new_lib = b"/tmp/dlpulse-wk/webkit2gtk-4.0".ljust(len(old_lib), b"\0")
old_inj = b"/usr/lib/x86_64-linux-gnu/webkit2gtk-4.0/injected-bundle/"
new_inj = b"/tmp/dlpulse-wk/webkit2gtk-4.0/injected-bundle/".ljust(len(old_inj), b"\0")
orig = data
if old_inj in data:
    data = data.replace(old_inj, new_inj)
if old_lib in data:
    data = data.replace(old_lib, new_lib)
if data != orig:
    with open(path, "wb") as f:
        f.write(data)
    print(f"bundle_gtk_webkit: patched WebKit paths in {path}")
PY
}

copy_lib() {
  local src="$1"
  [[ -f "$src" ]] || return 0
  local base dest
  base="$(basename "$src")"
  is_blocked "$base" && return 0
  dest="$ARCH_LIB/$base"
  if [[ -f "$dest" ]]; then
    return 0
  fi
  install -m 0755 "$src" "$dest"
}

copy_libs_from_binary() {
  local bin="$1"
  [[ -x "$bin" ]] || return 0
  while IFS= read -r lib; do
    [[ -n "$lib" && -f "$lib" ]] || continue
    copy_lib "$lib"
  done < <(ldd "$bin" 2>/dev/null | awk '/=> \// { print $3 }')
}

echo "bundle_gtk_webkit: WebKit/GTK libraries (not from PyInstaller exe — avoids libc dupes)"

# WebKit subprocess tree (helpers, injected-bundle, etc.) — hard-coded under webkit2gtk-4.0.
WEBKIT_SRC="/usr/lib/x86_64-linux-gnu/webkit2gtk-4.0"
WEBKIT_DST="$ARCH_LIB/webkit2gtk-4.0"
if [[ -d "$WEBKIT_SRC" ]]; then
  echo "bundle_gtk_webkit: WebKit tree from $WEBKIT_SRC"
  rm -rf "$WEBKIT_DST"
  mkdir -p "$WEBKIT_DST"
  cp -a "$WEBKIT_SRC"/. "$WEBKIT_DST/"
  shopt -s nullglob
  for helper in "$WEBKIT_DST"/WebKitWebProcess "$WEBKIT_DST"/WebKitNetworkProcess \
    "$WEBKIT_DST"/WebKitGPUProcess "$WEBKIT_DST"/injected-bundle/*.so*; do
    [[ -e "$helper" ]] || continue
    [[ -f "$helper" && ! -x "$helper" ]] && copy_lib "$helper"
    [[ -x "$helper" ]] && copy_libs_from_binary "$helper"
  done
  if [[ ! -f "$WEBKIT_DST/injected-bundle/libwebkit2gtkinjectedbundle.so" ]]; then
    echo "bundle_gtk_webkit: WARN missing injected-bundle on build host" >&2
  fi
fi

# Pull deps for WebKit/GI stack if present on the build host.
for seed in \
  /usr/lib/x86_64-linux-gnu/libwebkit2gtk-4.0.so.* \
  /usr/lib/x86_64-linux-gnu/libjavascriptcoregtk-4.0.so.* \
  /usr/lib/x86_64-linux-gnu/libgirepository-1.0.so.* \
  /usr/lib/x86_64-linux-gnu/libgtk-3.so.* \
  /usr/lib/x86_64-linux-gnu/libgdk-3.so.* \
  /usr/lib/x86_64-linux-gnu/libsoup-2.4.so.*
do
  [[ -f "$seed" ]] || continue
  copy_lib "$seed"
  copy_libs_from_binary "$seed"
done

# Resolve transitive deps (libs copied above only — never scan PyInstaller exe).
for _pass in 1 2 3 4; do
  while IFS= read -r so; do
    copy_libs_from_binary "$so"
  done < <(find "$ARCH_LIB" -maxdepth 1 -name '*.so*' -type f 2>/dev/null)
done

# GObject introspection typelibs — copy full set from build host (typelibs are tiny;
# partial lists miss deps like cairo-1.0 vs Cairo-1.0 naming on Debian/Ubuntu).
GIR_SRC="/usr/lib/x86_64-linux-gnu/girepository-1.0"
if [[ -d "$GIR_SRC" ]]; then
  echo "bundle_gtk_webkit: GIR typelibs from $GIR_SRC"
  shopt -s nullglob
  for gir in "$GIR_SRC"/*.typelib; do
    install -m 0644 "$gir" "$GIRDIR/$(basename "$gir")"
  done
  echo "bundle_gtk_webkit: $(find "$GIRDIR" -maxdepth 1 -name '*.typelib' | wc -l) typelibs"
fi

# GLib schemas (GTK settings).
if compgen -G "/usr/share/glib-2.0/schemas/*.gschemas.compiled" >/dev/null; then
  cp -a /usr/share/glib-2.0/schemas/* "$APPDIR/usr/share/glib-2.0/schemas/" 2>/dev/null || true
elif command -v glib-compile-schemas >/dev/null; then
  cp -a /usr/share/glib-2.0/schemas/*.xml "$APPDIR/usr/share/glib-2.0/schemas/" 2>/dev/null || true
  glib-compile-schemas "$APPDIR/usr/share/glib-2.0/schemas"
fi

# GdkPixbuf loaders (icons in UI).
PIXBUF_SRC="/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0"
PIXBUF_DST="$ARCH_LIB/gdk-pixbuf-2.0"
if [[ -d "$PIXBUF_SRC" ]] && command -v gdk-pixbuf-query-loaders >/dev/null; then
  echo "bundle_gtk_webkit: gdk-pixbuf loaders"
  rm -rf "$PIXBUF_DST"
  mkdir -p "$PIXBUF_DST"
  cp -a "$PIXBUF_SRC"/. "$PIXBUF_DST/"
  gdk-pixbuf-query-loaders > "$PIXBUF_DST/loaders.cache"
  sed -i "s|/usr/lib/x86_64-linux-gnu|$ARCH_LIB|g" "$PIXBUF_DST/loaders.cache" || true
fi

# Fontconfig (WebKit/GTK text rendering).
if [[ -d /etc/fonts ]]; then
  echo "bundle_gtk_webkit: fontconfig"
  mkdir -p "$APPDIR/etc/fonts"
  cp -a /etc/fonts/. "$APPDIR/etc/fonts/" 2>/dev/null || true
  # Rewrite absolute paths in fonts.conf to AppDir-relative where needed.
  if [[ -f "$APPDIR/etc/fonts/fonts.conf" ]]; then
    sed -i "s|/usr/share/fonts|$APPDIR/usr/share/fonts|g" "$APPDIR/etc/fonts/fonts.conf" || true
  fi
fi
mkdir -p "$APPDIR/usr/share/fonts"
if [[ -d /usr/share/fonts/truetype/dejavu ]]; then
  cp -a /usr/share/fonts/truetype/dejavu "$APPDIR/usr/share/fonts/" 2>/dev/null || true
fi

# Drop GPU/display libs — host Mesa + X11/Wayland must be used at runtime.
shopt -s nullglob
for _so in "$ARCH_LIB"/*.so*; do
  base="$(basename "$_so")"
  if is_blocked "$base"; then
    rm -f "$_so"
  fi
done

# Repoint hardcoded WebKit helper paths for distros without Ubuntu's layout (Arch, Fedora, etc.).
for _wk in "$ARCH_LIB"/libwebkit2gtk-4.0.so*; do
  patch_webkit_paths "$_wk"
done

echo "bundle_gtk_webkit: done ($(find "$ARCH_LIB" -maxdepth 1 -name '*.so*' 2>/dev/null | wc -l) libraries under usr/lib/x86_64-linux-gnu)"
