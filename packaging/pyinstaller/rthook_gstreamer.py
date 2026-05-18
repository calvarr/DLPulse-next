# WebKit media uses GStreamer. PyInstaller's _internal must not be scanned as plugins.
# Runs after PyInstaller sets LD_LIBRARY_PATH — reorder so host GLib/GStreamer win.
import os

_MEIPASS = os.environ.get("_MEIPASS", "")


def _reorder_ld_library_path() -> None:
    if not _MEIPASS:
        return
    sys_paths = ["/usr/lib", "/usr/lib64"]
    parts = [p for p in os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep) if p]
    other: list[str] = []
    seen = set(sys_paths)
    for p in parts:
        if p == _MEIPASS or p.endswith("/_internal"):
            continue
        if p in seen:
            continue
        other.append(p)
        seen.add(p)
    ordered = sys_paths + other + [_MEIPASS]
    os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(ordered)


_reorder_ld_library_path()

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
    os.environ["GST_PLUGIN_SYSTEM_PATH"] = _joined
    os.environ.pop("GST_PLUGIN_PATH", None)

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
