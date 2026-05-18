"""Optional native folder picker (zenity / AppleScript / PowerShell) for session download folder."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def pick_folder_dialog(start_dir: str | None = None, *, title: str = "Choose download folder") -> str | None:
    start = (start_dir or "").strip()
    if start and not os.path.isdir(start):
        start = str(Path.home())

    if sys.platform == "linux":
        zen = shutil.which("zenity")
        if zen:
            args = [zen, "--file-selection", "--directory", f"--title={title}"]
            if start:
                args.append(f"--filename={start}/")
            try:
                r = subprocess.run(args, capture_output=True, text=True, timeout=300, check=False)
                if r.returncode == 0 and (p := (r.stdout or "").strip()):
                    return p
            except (OSError, subprocess.TimeoutExpired):
                pass
        kd = shutil.which("kdialog")
        if kd:
            try:
                r = subprocess.run(
                    [kd, "--getexistingdirectory", start or str(Path.home())],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    check=False,
                )
                if r.returncode == 0 and (p := (r.stdout or "").strip().strip("\n")):
                    return p
            except (OSError, subprocess.TimeoutExpired):
                pass

    if sys.platform == "darwin":
        try:
            r = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'POSIX path of (choose folder with prompt "Choose download folder")',
                ],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            out = (r.stdout or "").strip().rstrip("/\n")
            if out and os.path.isdir(out):
                return out
        except (OSError, subprocess.TimeoutExpired):
            pass

    if sys.platform == "win32":
        sp = (start or "").replace("'", "''")
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
            "$f.Description = 'Choose download folder'; "
            f"$f.SelectedPath = '{sp}'; "
            "if ($f.ShowDialog() -eq 'OK') { $f.SelectedPath }"
        )
        pw = shutil.which("powershell.exe") or shutil.which("pwsh")
        if pw:
            try:
                r = subprocess.run(
                    [pw, "-NoProfile", "-Sta", "-Command", ps],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    check=False,
                )
                p = (r.stdout or "").strip()
                if p and os.path.isdir(p):
                    return p
            except (OSError, subprocess.TimeoutExpired):
                pass

    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        d = filedialog.askdirectory(title=title, initialdir=start or None)
        root.destroy()
        return d or None
    except Exception:
        return None
