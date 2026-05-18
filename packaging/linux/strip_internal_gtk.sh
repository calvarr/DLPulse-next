#!/usr/bin/env bash
# PyInstaller copies many Ubuntu .so files into _internal/ root. On Arch/Fedora they
# shadow newer system libs and break GObject introspection (libgio → libmount → libsystemd).
# Python extensions live in subdirs; keep only libs the frozen runtime truly needs here.
set -euo pipefail

INTERNAL="${1:?Usage: strip_internal_gtk.sh path/to/_internal}"

[[ -d "$INTERNAL" ]] || exit 0

KEEP_ROOT_LIBS=(
  libpython3.12.so.1.0
  libaria2.so.0
)

should_keep() {
  local base="$1"
  local k
  for k in "${KEEP_ROOT_LIBS[@]}"; do
    [[ "$base" == "$k" || "$base" == "$k."* ]] && return 0
  done
  return 1
}

removed=0
shopt -s nullglob
for _so in "$INTERNAL"/lib*.so*; do
  base="$(basename "$_so")"
  if should_keep "$base"; then
    continue
  fi
  rm -f "$_so"
  removed=$((removed + 1))
done

echo "strip_internal_gtk: removed $removed bundled system libs from _internal (kept libpython + libaria2)"
