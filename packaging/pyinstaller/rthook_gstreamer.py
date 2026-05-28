# WebKit media uses GStreamer. PyInstaller's _internal must not be scanned as plugins.
# Runs after PyInstaller sets LD_LIBRARY_PATH — reorder so host GLib/GStreamer win.
#
# Exception: in the SELF-CONTAINED AppImage (AppRun sets DLPULSE_SELFCONTAINED=1)
# the whole GTK/WebKit/GStreamer stack is bundled and AppRun has already pointed
# every variable at the bundle. Reordering toward host /usr/lib would load host
# libraries instead and defeat self-containment, so we leave AppRun's env alone.
import os

_MEIPASS = os.environ.get("_MEIPASS", "")
_SELF_CONTAINED = (
    os.environ.get("DLPULSE_SELFCONTAINED") == "1" and bool(os.environ.get("APPDIR"))
)


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


def _configure_host_gstreamer() -> None:
    gst_dirs: list[str] = []
    for p in (
        "/usr/lib/gstreamer-1.0",
        "/usr/lib64/gstreamer-1.0",
        "/usr/lib/x86_64-linux-gnu/gstreamer-1.0",
    ):
        if os.path.isdir(p):
            gst_dirs.append(p)

    if gst_dirs:
        os.environ["GST_PLUGIN_SYSTEM_PATH"] = os.pathsep.join(gst_dirs)
        os.environ.pop("GST_PLUGIN_PATH", None)

    for scanner in (
        "/usr/libexec/gstreamer-1.0/gst-plugin-scanner",
        "/usr/lib/gstreamer-1.0/gst-plugin-scanner",
    ):
        if os.path.isfile(scanner):
            os.environ["GST_PLUGIN_SCANNER"] = scanner
            break

    cache = os.path.join(
        os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
        "dlpulse-next",
    )
    try:
        os.makedirs(cache, exist_ok=True)
        os.environ["GST_REGISTRY"] = os.path.join(cache, "gstreamer-registry.bin")
    except OSError:
        pass


if not _SELF_CONTAINED:
    _reorder_ld_library_path()
    _configure_host_gstreamer()
