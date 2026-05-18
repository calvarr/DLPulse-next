#!/usr/bin/env bash
# Remove GTK/WebKit libs PyInstaller may collect — runtime uses system packages.
set -euo pipefail

INTERNAL="${1:?Usage: strip_internal_gtk.sh path/to/_internal}"

[[ -d "$INTERNAL" ]] || exit 0

STRIP=(
  libglib-2.0.so.0
  libgobject-2.0.so.0
  libgio-2.0.so.0
  libgmodule-2.0.so.0
  libgirepository-1.0.so.1
  libgtk-3.so.0
  libgdk-3.so.0
  libgdk_pixbuf-2.0.so.0
  libatk-1.0.so.0
  libatk-bridge-2.0.so.0
  libatspi.so.0
  libpango-1.0.so.0
  libpangocairo-1.0.so.0
  libpangoft2-1.0.so.0
  libcairo.so.2
  libcairo-gobject.so.2
  libharfbuzz.so.0
  libfribidi.so.0
  libepoxy.so.0
  libwebkit2gtk-4.0.so.37
  libwebkit2gtk-4.1.so.0
  libjavascriptcoregtk-4.0.so.18
  libjavascriptcoregtk-4.1.so.0
  libstdc++.so.6
  libgcc_s.so.1
)

for lib in "${STRIP[@]}"; do
  rm -f "$INTERNAL/$lib"
done

# Versioned sonames (e.g. libwebkit2gtk-4.1.so.0.24.3)
shopt -s nullglob
for _so in "$INTERNAL"/libwebkit2gtk-*.so* "$INTERNAL"/libjavascriptcoregtk-*.so*; do
  rm -f "$_so"
done
