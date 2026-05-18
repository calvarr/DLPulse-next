# Linux pywebview: match system WebKit2GTK (4.1 + Soup 3.0, or 4.0 + Soup 2.4).
import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
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
