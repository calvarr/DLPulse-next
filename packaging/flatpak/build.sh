#!/usr/bin/env bash
# Build and install DLPulse Next Flatpak for the current user.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANIFEST="$ROOT/packaging/flatpak/com.github.calvarr.DLPulseNext.yml"
BUILD_DIR="$ROOT/build-flatpak"

echo "Manifest: $MANIFEST"
echo "Build dir: $BUILD_DIR"
echo
echo "Ensure runtime is installed:"
echo "  flatpak install flathub org.gnome.Platform//49 org.gnome.Sdk//49"
echo

flatpak-builder --user --install --force-clean "$BUILD_DIR" "$MANIFEST"

echo
echo "Installed. Run:"
echo "  flatpak run com.github.calvarr.DLPulseNext"
