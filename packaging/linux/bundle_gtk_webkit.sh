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
)

is_blocked() {
  local base="$1"
  local blocked
  for blocked in "${NEVER_BUNDLE[@]}"; do
    [[ "$base" == "$blocked" || "$base" == "$blocked."* ]] && return 0
  done
  return 1
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

# WebKit subprocess helpers (hard-coded paths at WebKit build time).
WEBKIT_SRC="/usr/lib/x86_64-linux-gnu/webkit2gtk-4.0"
WEBKIT_DST="$ARCH_LIB/webkit2gtk-4.0"
if [[ -d "$WEBKIT_SRC" ]]; then
  echo "bundle_gtk_webkit: WebKit helpers from $WEBKIT_SRC"
  mkdir -p "$WEBKIT_DST"
  shopt -s nullglob
  for helper in "$WEBKIT_SRC"/WebKitWebProcess "$WEBKIT_SRC"/WebKitNetworkProcess; do
    [[ -x "$helper" ]] || continue
    install -m 0755 "$helper" "$WEBKIT_DST/$(basename "$helper")"
    copy_libs_from_binary "$helper"
  done
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

# GObject introspection typelibs required by pywebview GTK backend.
GIR_SRC="/usr/lib/x86_64-linux-gnu/girepository-1.0"
if [[ -d "$GIR_SRC" ]]; then
  echo "bundle_gtk_webkit: GIR typelibs"
  for gir in \
    GLib-2.0.typelib GObject-2.0.typelib Gio-2.0.typelib \
    Gdk-3.0.typelib Gtk-3.0.typelib Pango-1.0.typelib \
    Cairo-1.0.typelib GdkPixbuf-2.0.typelib \
    JavaScriptCore-4.0.typelib WebKit2-4.0.typelib \
    Soup-2.4.typelib HarfBuzz-0.0.typelib \
    xlib-2.0.typelib Atk-1.0.typelib
  do
    [[ -f "$GIR_SRC/$gir" ]] && install -m 0644 "$GIR_SRC/$gir" "$GIRDIR/$gir"
  done
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

echo "bundle_gtk_webkit: done ($(find "$ARCH_LIB" -maxdepth 1 -name '*.so*' 2>/dev/null | wc -l) libraries under usr/lib/x86_64-linux-gnu)"
