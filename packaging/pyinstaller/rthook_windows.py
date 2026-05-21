# PyInstaller runtime hook — Windows (pythonnet / WebView2 DLL search path).
import os
import sys
from pathlib import Path

_meipass = getattr(sys, "_MEIPASS", "") or os.environ.get("_MEIPASS", "")
if _meipass:
    os.environ["PATH"] = _meipass + os.pathsep + os.environ.get("PATH", "")
os.environ.setdefault("PYTHONNET_RUNTIME", "coreclr")
_cfg = Path(_meipass) / "windows_runtimeconfig.json" if _meipass else None
if _cfg and _cfg.is_file():
    os.environ["PYTHONNET_CORECLR_RUNTIME_CONFIG"] = str(_cfg.resolve())
