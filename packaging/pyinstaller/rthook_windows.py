# PyInstaller runtime hook — Windows (pythonnet / WebView2 / PATH).
# Runs before the app imports; must not import dlpulse_next (not on path yet).
import os
import sys
from pathlib import Path

_meipass = getattr(sys, "_MEIPASS", "") or os.environ.get("_MEIPASS", "")
_roots: list[Path] = []
_dotnet_root: str | None = None
if _meipass:
    _roots.append(Path(_meipass))
if getattr(sys, "frozen", False):
    _exe_dir = Path(sys.executable).resolve().parent
    _roots.append(_exe_dir)
    _internal = _exe_dir / "_internal"
    if _internal.is_dir():
        _roots.append(_internal)
    _bundled_dotnet = None
    for _dotnet_rel in ("dotnet", "_internal/dotnet"):
        _cand = _exe_dir / _dotnet_rel
        if (_cand / "host" / "fxr").is_dir():
            _bundled_dotnet = _cand
            break
    if _bundled_dotnet is not None:
        _dotnet_root = str(_bundled_dotnet.resolve())
    else:
        _sys_dotnet = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "dotnet"
        if (_sys_dotnet / "host" / "fxr").is_dir():
            _dotnet_root = str(_sys_dotnet.resolve())
    if _dotnet_root:
        os.environ["DOTNET_ROOT"] = _dotnet_root
        os.environ["PYTHONNET_CORECLR_DOTNET_ROOT"] = _dotnet_root
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

os.environ.setdefault("PYTHONNET_RUNTIME", "coreclr")

for _root in _roots:
    _cfg = _root / "windows_runtimeconfig.json"
    if _cfg.is_file():
        os.environ["PYTHONNET_CORECLR_RUNTIME_CONFIG"] = str(_cfg.resolve())
        break

for _root in _roots:
    for _rel in ("pythonnet/runtime/Python.Runtime.dll", "runtime/Python.Runtime.dll"):
        _dll = _root / _rel
        if _dll.is_file():
            os.environ["PYTHONNET_PYDLL"] = str(_dll.resolve())
            break
    if os.environ.get("PYTHONNET_PYDLL"):
        break

_cfg_env = os.environ.get("PYTHONNET_CORECLR_RUNTIME_CONFIG", "")
try:
    from pythonnet import load

    _load_kw = {}
    if _cfg_env:
        _load_kw["runtime_config"] = _cfg_env
    if _dotnet_root:
        _load_kw["dotnet_root"] = _dotnet_root
    load("coreclr", **_load_kw)
except Exception:
    pass
