#!/usr/bin/env bash
# Remove GTK/GLib libs PyInstaller may collect — AppImage uses usr/lib/x86_64-linux-gnu instead.
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
  libstdc++.so.6
  libgcc_s.so.1
)

for lib in "${STRIP[@]}"; do
  rm -f "$INTERNAL/$lib"
done
