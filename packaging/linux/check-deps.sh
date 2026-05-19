#!/usr/bin/env bash
# Verify host packages for DLPulse Next AppImage (native window + playback).
set -euo pipefail

ok=0
warn=0
fail=0

check() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "OK   $label"
    ok=$((ok + 1))
  else
    echo "FAIL $label"
    fail=$((fail + 1))
  fi
}

warn_if() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "OK   $label"
    ok=$((ok + 1))
  else
    echo "WARN $label (optional but recommended)"
    warn=$((warn + 1))
  fi
}

echo "DLPulse Next — Linux dependency check"
echo

check "gtk3 + PyGObject" python3 -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk"
check "WebKit2GTK typelib" python3 -c "import gi; gi.require_version('WebKit2','4.1'); from gi.repository import WebKit2"
warn_if "GStreamer appsink" gst-inspect-1.0 appsink
warn_if "GStreamer autoaudiosink" gst-inspect-1.0 autoaudiosink
warn_if "mpv (external player)" command -v mpv

echo
echo "Summary: $ok ok, $warn optional missing, $fail required missing"
if [ "$fail" -gt 0 ]; then
  echo "Install packages listed in README.md (Linux — AppImage)."
  exit 1
fi
if [ "$warn" -gt 0 ]; then
  echo "In-app video may fail; use Settings → External player or install gstreamer plugins + mpv."
fi
