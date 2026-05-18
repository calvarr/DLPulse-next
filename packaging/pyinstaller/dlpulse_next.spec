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

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

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

_binaries = list(ff_binaries)

# Optional: aria2c staged under packaging/binaries/ (CI copies platform binary before PyInstaller).
_aria2_staged = SPECDIR.parent / "binaries" / ("aria2c.exe" if sys.platform == "win32" else "aria2c")
if _aria2_staged.is_file():
    _binaries.append((str(_aria2_staged), "."))

_hidden = list(ff_hidden)
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
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
