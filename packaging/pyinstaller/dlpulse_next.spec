# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: DLPulse Next (pywebview + Flask + yt-dlp + imageio-ffmpeg).
# Build from repo root:  pyinstaller packaging/pyinstaller/dlpulse_next.spec
# Produces dist/DLPulseNext/ (onedir) with bundled static UI, yt-dlp extractors, ffmpeg from imageio-ffmpeg.

import sys
from pathlib import Path

block_cipher = None

SPECDIR = Path(SPECPATH)
ROOT = SPECDIR.parent.parent.resolve()
PKG = ROOT / "dlpulse_next"

sys.path.insert(0, str(ROOT))

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

ff_datas, ff_binaries, ff_hidden = collect_all("imageio_ffmpeg")

_datas = [(str(PKG / "static"), "dlpulse_next/static")]
_datas += ff_datas
_datas += collect_data_files("certifi")

_commit = PKG / "build_commit.txt"
if _commit.is_file():
    _datas.append((str(_commit), "dlpulse_next"))

_version = PKG / "build_version.txt"
if _version.is_file():
    _datas.append((str(_version), "dlpulse_next"))

if sys.platform == "win32":
    _win_rt = SPECDIR / "windows_runtimeconfig.json"
    if _win_rt.is_file():
        _datas.append((str(_win_rt), "."))

_binaries = list(ff_binaries)

_hidden = list(ff_hidden)

# Optional: aria2c staged under packaging/binaries/ (CI copies platform binary before PyInstaller).
_aria2_staged = SPECDIR.parent / "binaries" / ("aria2c.exe" if sys.platform == "win32" else "aria2c")
if _aria2_staged.is_file():
    _binaries.append((str(_aria2_staged), "."))

# macOS: aria2 1.37 hard-loads OpenSSL's "legacy" provider on startup; bundle
# the provider plug-in so the app runs on machines without Homebrew installed.
# packaging/macos/make_dmg.sh patches its libcrypto reference and wraps aria2c
# with a launcher that sets OPENSSL_MODULES to this directory.
if sys.platform == "darwin":
    _ossl_legacy = SPECDIR.parent / "binaries" / "ossl-modules" / "legacy.dylib"
    if _ossl_legacy.is_file():
        _binaries.append((str(_ossl_legacy), "ossl-modules"))

if sys.platform.startswith("linux"):
    try:
        import gi as _gi_pkg
        from pathlib import Path as _Path

        _gi_dir = _Path(_gi_pkg.__file__).parent
        _datas.append((str(_gi_dir), "gi"))
        for _so in _gi_dir.glob("_gi*.so"):
            _binaries.append((str(_so), "gi"))
        _hidden += collect_submodules("gi")
        _hidden += [
            "gi._gi",
            "gi.repository.WebKit2",
            "gi.repository.Gtk",
            "gi.repository.GLib",
            "gi.repository.Gio",
            "gi.repository.Gdk",
        ]
    except Exception:
        pass

_hookspath: list[str] = []
try:
    import webview as _webview_pkg

    _hookspath.append(str(Path(_webview_pkg.__file__).resolve().parent / "__pyinstaller"))
except Exception:
    pass

_runtime_hooks: list[str] = []
if sys.platform.startswith("linux"):
    _runtime_hooks.append(str(SPECDIR / "rthook_gstreamer.py"))
    _runtime_hooks.append(str(SPECDIR / "rthook_gtk.py"))
elif sys.platform == "win32":
    _runtime_hooks.append(str(SPECDIR / "rthook_windows.py"))
    for _mod in ("pythonnet", "clr_loader", "clr"):
        try:
            _d, _b, _h = collect_all(_mod)
            _datas += _d
            _binaries += _b
            _hidden += _h
        except Exception as _e:
            print(f"WARNING: collect_all({_mod}) failed: {_e}", file=sys.stderr)
    try:
        import pythonnet as _pn

        _pn_root = Path(_pn.__file__).resolve().parent
        _rt = _pn_root / "runtime"
        if _rt.is_dir():
            _datas.append((str(_rt), "pythonnet/runtime"))
    except Exception as _e:
        print(f"WARNING: pythonnet runtime collect failed: {_e}", file=sys.stderr)
    try:
        _datas += collect_data_files("webview", subdir="lib")
        _datas += collect_data_files("webview", subdir="js")
        _binaries += collect_dynamic_libs("webview")
    except Exception as _e:
        print(f"WARNING: webview DLL collect failed: {_e}", file=sys.stderr)
    _hidden += [
        "clr",
        "pythonnet",
        "clr_loader",
        "clr_loader.ffi",
        "clr_loader.util",
        "clr_loader.util.find",
        "clr_loader.util.coreclr_errors",
        "clr_loader.hostfxr",
        "clr_loader.netfx",
    ]

_hidden += collect_submodules("yt_dlp")
_hidden += [
    "yt_dlp",
    "flask",
    "werkzeug",
    "jinja2",
    "itsdangerous",
    "click",
    "blinker",
    "webview",
    "webview.http",
    "bottle",
    "mutagen",
    "zeroconf",
    "zeroconf._utils.ipaddress",
    "pychromecast",
    "pychromecast.controllers",
    "ifaddr",
    "qrcode",
    "qrcode.image.svg",
    "packaging",
    "packaging.version",
    "importlib.metadata",
    "importlib.resources",
]

# Platform backends for pywebview (harmless extras on other OS).
_hidden += [
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "webview.platforms.mshtml",
    "webview.platforms.cocoa",
    "webview.platforms.gtk",
    "webview.platforms.qt",
]

a = Analysis(
    [str(PKG / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=_binaries,
    datas=_datas,
    hiddenimports=_hidden,
    hookspath=_hookspath,
    hooksconfig={},
    runtime_hooks=_runtime_hooks,
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "PIL", "IPython", "pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

_icon = PKG / "static" / "dlpulse_icon.ico"
if not _icon.is_file():
    _icon = PKG / "static" / "dlpulse_icon.png"

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DLPulseNext",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(_icon) if _icon.is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DLPulseNext",
)
