# WebKit media uses GStreamer. PyInstaller's _internal must not be scanned as a plugin dir.
import os

_gst_dirs: list[str] = []
for _p in (
    "/usr/lib/gstreamer-1.0",
    "/usr/lib64/gstreamer-1.0",
    "/usr/lib/x86_64-linux-gnu/gstreamer-1.0",
):
    if os.path.isdir(_p):
        _gst_dirs.append(_p)

if _gst_dirs:
    _joined = os.pathsep.join(_gst_dirs)
    os.environ["GST_PLUGIN_PATH"] = _joined
    os.environ["GST_PLUGIN_SYSTEM_PATH"] = _joined

for _scanner in (
    "/usr/libexec/gstreamer-1.0/gst-plugin-scanner",
    "/usr/lib/gstreamer-1.0/gst-plugin-scanner",
):
    if os.path.isfile(_scanner):
        os.environ["GST_PLUGIN_SCANNER"] = _scanner
        break

_cache = os.path.join(
    os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
    "dlpulse-next",
)
try:
    os.makedirs(_cache, exist_ok=True)
    os.environ["GST_REGISTRY"] = os.path.join(_cache, "gstreamer-registry.bin")
except OSError:
    pass
