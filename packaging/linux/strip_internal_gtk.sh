#!/usr/bin/env bash
# PyInstaller copies the build-host GLib / GTK / GIO stack into _internal/. On
# rolling distros (Arch / Fedora) those shadow newer system libs and break
# GObject introspection (libgio -> libmount -> libsystemd) and WebKit2.
#
# Removing them at the _internal/ root forces the host GLib/GTK to be used at
# runtime. PyInstaller's Python extensions in subdirs (Python stdlib, ssl, etc.)
# are left alone.
set -euo pipefail

INTERNAL="${1:?Usage: strip_internal_gtk.sh path/to/_internal}"

[[ -d "$INTERNAL" ]] || exit 0

# Library name prefixes that must come from the host (never from _internal/).
#
# libstdc++ / libgcc_s: the build host (Ubuntu 22.04, older GCC) ships an older
# libstdc++ than rolling distros. Host WebKit/ICU (e.g. libicui18n) require a
# newer CXXABI (1.3.15+), so the bundled libstdc++ breaks the typelib load with
# "version CXXABI_1.3.15 not found". Dropping them forces the newer host copy.
SHADOW_PREFIXES=(
  libstdc++
  libgcc_s
  libglib-2.0
  libgio-2.0
  libgobject-2.0
  libgmodule-2.0
  libgthread-2.0
  libgirepository-1.0
  libffi
  libmount
  libblkid
  libuuid
  libsystemd
  libudev
  libdbus-1
  libdbus-glib-1
  libpcre
  libpcre2-8
  libselinux
  libz
  libcairo
  libcairo-gobject
  libpango-1.0
  libpangocairo-1.0
  libpangoft2-1.0
  libgdk_pixbuf-2.0
  libgdk-3
  libgtk-3
  libatk-1.0
  libatk-bridge-2.0
  libatspi
  libwebkit2gtk-4.0
  libwebkit2gtk-4.1
  libjavascriptcoregtk-4.0
  libjavascriptcoregtk-4.1
  libsoup-2.4
  libsoup-3.0
  libxml2
  libsqlite3
  libgcrypt
  libgnutls
  libtasn1
  libnettle
  libhogweed
  libgmp
  libidn2
  libunistring
  libgssapi_krb5
  libkrb5
  libk5crypto
  libcom_err
  libkrb5support
  libssl
  libcrypto
  libharfbuzz
  libfontconfig
  libfreetype
  libfribidi
  libthai
  libdatrie
  libgraphite2
  libgst
  # WebKit/GTK transitive deps: on rolling distros the host copies of these are
  # newer and their symbols are pulled in by host WebKit/GTK/curl, so the older
  # bundled versions break loading (undefined symbols / version mismatches).
  libgpg-error
  libp11-kit
  libproxy
  librsvg-2
  libepoxy
  libxkbcommon
  libssh2
  libX11
  libXau
  libXdmcp
  libxcb
  libxcb-render
  libxcb-shm
  libXcomposite
  libXcursor
  libXdamage
  libXext
  libXfixes
  libXi
  libXinerama
  libXrandr
  libXrender
  libpixman-1
  libpng16
  libjpeg
  libtiff
  libwebp
  libjbig
  libbrotlicommon
  libbrotlidec
  libbz2
  liblz4
  liblzma
  libzstd
  libdeflate
  libexpat
  libbsd
  libmd
  libcap
)

should_remove() {
  local base="$1"
  local prefix
  for prefix in "${SHADOW_PREFIXES[@]}"; do
    if [[ "$base" == "$prefix.so" || "$base" == "$prefix.so."* ]]; then
      return 0
    fi
  done
  return 1
}

removed=0
shopt -s nullglob
for _so in "$INTERNAL"/lib*.so*; do
  base="$(basename "$_so")"
  if should_remove "$base"; then
    rm -f "$_so"
    removed=$((removed + 1))
  fi
done

echo "strip_internal_gtk: removed $removed bundled GTK/GLib libs from _internal (host versions will be used)"
