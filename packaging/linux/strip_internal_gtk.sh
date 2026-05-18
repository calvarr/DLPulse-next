#!/usr/bin/env bash
# Remove libs PyInstaller may collect from Ubuntu CI that shadow the host GLib/GTK stack.
# System WebKit/GTK/GIO must load /usr/lib/* (e.g. libmount with MOUNT_2_40 on Arch).
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
  libmount.so.1
  libblkid.so.1
  libuuid.so.1
  libselinux.so.1
  libpcre2-8.so.0
  libpcre.so.3
  libsoup-2.4.so.1
  libsoup-3.0.so.0
  libstdc++.so.6
  libgcc_s.so.1
)

for lib in "${STRIP[@]}"; do
  rm -f "$INTERNAL/$lib"
done

shopt -s nullglob
for _pat in \
  libwebkit2gtk-*.so* \
  libjavascriptcoregtk-*.so* \
  libsoup-*.so* \
  libmount.so* \
  libblkid.so* \
  libuuid.so*
do
  for _so in "$INTERNAL"/$_pat; do
    rm -f "$_so"
  done
done

echo "strip_internal_gtk: removed host-conflicting libs from $(basename "$(dirname "$INTERNAL")")/_internal"
