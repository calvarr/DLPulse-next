# PyInstaller runtime hook — Windows (pythonnet / WebView2 DLL search path).
import os
import sys

_meipass = getattr(sys, "_MEIPASS", "") or os.environ.get("_MEIPASS", "")
if _meipass:
    os.environ["PATH"] = _meipass + os.pathsep + os.environ.get("PATH", "")
os.environ.setdefault("PYTHONNET_RUNTIME", "coreclr")
