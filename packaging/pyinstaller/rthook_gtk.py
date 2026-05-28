# Linux pywebview: match system WebKit2GTK (4.1 + Soup 3.0, or 4.0 + Soup 2.4).
import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

# In the self-contained AppImage, AppRun exports the EXACT WebKit/Soup versions
# that were bundled (DLPULSE_WEBKIT_VER / DLPULSE_SOUP_VER). Pin them so that
# gobject-introspection uses the bundled typelib instead of falling through to a
# different host typelib — e.g. requesting 4.1 first on a host that has 4.1 would
# dlopen the host libwebkit2gtk-4.1 and drag in mismatched host libs (libicu/
# libstdc++ CXXABI clash).
_wk_ver = os.environ.get("DLPULSE_WEBKIT_VER")
_soup_ver = os.environ.get("DLPULSE_SOUP_VER")
if _wk_ver:
    gi.require_version("WebKit2", _wk_ver)
    if _soup_ver:
        try:
            gi.require_version("Soup", _soup_ver)
        except ValueError:
            pass
else:
    try:
        gi.require_version("WebKit2", "4.1")
        gi.require_version("Soup", "3.0")
    except ValueError:
        gi.require_version("WebKit2", "4.0")
        gi.require_version("Soup", "2.4")

# PyInstaller/AppImage: WebKit subprocess sandbox cannot see host GStreamer plugins.
if os.environ.get("_MEIPASS") or os.environ.get("APPIMAGE"):
    os.environ["WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS"] = "1"

from gi.repository import WebKit2  # noqa: E402

_ctx = WebKit2.WebContext.get_default()
for _gst_path in (
    "/usr/lib/gstreamer-1.0",
    "/usr/lib64/gstreamer-1.0",
    "/usr/lib/x86_64-linux-gnu/gstreamer-1.0",
    "/usr/libexec/gstreamer-1.0",
):
    if os.path.isdir(_gst_path):
        try:
            _ctx.add_path_to_sandbox(_gst_path, True)
        except Exception:
            pass
