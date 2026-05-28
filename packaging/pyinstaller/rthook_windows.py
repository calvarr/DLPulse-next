# PyInstaller runtime hook — Windows (pythonnet / WebView2 / PATH).
# Runs before the app imports; must not import dlpulse_next (not on path yet).
import os
import sys
from pathlib import Path

_meipass = getattr(sys, "_MEIPASS", "") or os.environ.get("_MEIPASS", "")
_roots: list[Path] = []
if _meipass:
    _roots.append(Path(_meipass))
if getattr(sys, "frozen", False):
    _exe_dir = Path(sys.executable).resolve().parent
    _roots.append(_exe_dir)
    _internal = _exe_dir / "_internal"
    if _internal.is_dir():
        _roots.append(_internal)
    _bundled_wv2 = None
    for _wv2_rel in ("WebView2Runtime", "_internal/WebView2Runtime"):
        _cand = _exe_dir / _wv2_rel
        if _cand.is_dir():
            _bundled_wv2 = _cand
            break
    if _bundled_wv2 is not None:
        for _wv2exe in _bundled_wv2.rglob("msedgewebview2.exe"):
            os.environ["DLPULSE_WEBVIEW2_RUNTIME"] = str(_wv2exe.parent.resolve())
            break

_path = os.environ.get("PATH", "")
for _r in reversed(_roots):
    s = str(_r)
    if s and s not in _path.split(os.pathsep):
        _path = s + os.pathsep + _path
os.environ["PATH"] = _path

# pywebview WinForms + WebView2 interop needs .NET Framework via pythonnet (not CoreCLR).
# Do not preload CoreCLR here — dlpulse_next.windows_pythonnet.bootstrap_pythonnet() loads netfx first.
os.environ["PYTHONNET_RUNTIME"] = "netfx"

for _root in _roots:
    for _rel in ("pythonnet/runtime/Python.Runtime.dll", "runtime/Python.Runtime.dll"):
        _dll = _root / _rel
        if _dll.is_file():
            os.environ["PYTHONNET_PYDLL"] = str(_dll.resolve())
            break
    if os.environ.get("PYTHONNET_PYDLL"):
        break

for _root in _roots:
    _cfg = _root / "windows_runtimeconfig.json"
    if _cfg.is_file():
        os.environ["PYTHONNET_CORECLR_RUNTIME_CONFIG"] = str(_cfg.resolve())
        break
