"""In-app folder browser (ported from ``yt/flet_app/file_browser_dialog.py``)."""

from __future__ import annotations

import os
import re
import shutil
import stat
import string
import sys
from pathlib import Path
from typing import Any

from dlpulse_next.media_paths import is_media_path


def expand_initial(initial: str | Path | None) -> Path:
    if not initial:
        return Path.home().absolute()
    p = Path(os.path.expanduser(str(initial)))
    try:
        if p.is_dir():
            with os.scandir(p):
                pass
            return p.absolute()
    except OSError:
        pass
    return Path.home().absolute()


def safe_name(name: str) -> bool:
    name = name.strip()
    if not name or name in (".", ".."):
        return False
    if ".." in name or "/" in name or "\\" in name:
        return False
    if sys.platform == "win32" and re.search(r'[<>:"|?*]', name):
        return False
    return True


def path_for_navigation(raw: str) -> tuple[Path | None, str | None]:
    raw = (raw or "").strip()
    if not raw:
        return None, "Enter a path."
    expanded = os.path.expanduser(raw)
    try:
        p = Path(expanded).absolute()
    except OSError as e:
        return None, str(e)
    try:
        st = p.stat()
    except OSError as e:
        return None, str(e)
    if not stat.S_ISDIR(st.st_mode):
        return None, "Not a directory."
    try:
        with os.scandir(p) as it:
            next(it, None)
    except OSError as e:
        return None, str(e)
    return p, None


def list_entries(
    path: Path, *, media_only: bool = True
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    dirs: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    err: str | None = None
    try:
        if not path.is_dir():
            return [], [], "Not a directory"
        for ch in sorted(path.iterdir(), key=lambda x: x.name.lower()):
            try:
                is_dir = ch.is_dir()
                if is_dir and ch.name.startswith("."):
                    continue
                row = {
                    "name": ch.name,
                    "path": str(ch.absolute()),
                    "is_dir": is_dir,
                }
                if is_dir:
                    dirs.append(row)
                elif not media_only or is_media_path(ch):
                    files.append(row)
            except OSError:
                continue
    except OSError as e:
        err = str(e)
        if getattr(e, "errno", None) == 13:
            err = f"{e} (cannot list this folder — choose a location you can read.)"
    return dirs, files, err


def windows_drives() -> list[str]:
    out: list[str] = []
    for d in string.ascii_uppercase:
        r = f"{d}:/"
        try:
            if os.path.exists(r):
                out.append(str(Path(r).absolute()))
        except OSError:
            continue
    return out


def browse(
    path: str | None = None, *, initial: str | None = None, media_only: bool = True
) -> dict[str, Any]:
    if path:
        current, nav_err = path_for_navigation(path)
        if current is None:
            return {"ok": False, "error": nav_err or "Invalid path."}
    else:
        current = expand_initial(initial)

    parent = current.parent
    can_go_up = parent != current
    show_drives = sys.platform == "win32" and not can_go_up

    dirs, files, err = list_entries(current, media_only=media_only)
    if err:
        return {"ok": False, "error": err, "path": str(current)}

    return {
        "ok": True,
        "path": str(current),
        "parent": str(parent) if can_go_up else None,
        "can_go_up": can_go_up,
        "drives": windows_drives() if show_drives else [],
        "dirs": dirs,
        "files": files,
    }


def mkdir(parent: str, name: str) -> dict[str, Any]:
    if not safe_name(name):
        return {"ok": False, "error": "Invalid folder name."}
    base, err = path_for_navigation(parent)
    if base is None:
        return {"ok": False, "error": err or "Invalid path."}
    dest = base / name.strip()
    try:
        dest.mkdir(mode=0o755, parents=False, exist_ok=False)
        if sys.platform != "win32":
            try:
                os.chmod(dest, 0o755)
            except OSError:
                pass
    except OSError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "path": str(dest)}


def rename_item(target: str, new_name: str) -> dict[str, Any]:
    if not safe_name(new_name):
        return {"ok": False, "error": "Invalid name."}
    p = Path(target).expanduser()
    try:
        p = p.absolute()
    except OSError as e:
        return {"ok": False, "error": str(e)}
    if not p.exists():
        return {"ok": False, "error": "Not found."}
    dest = p.parent / new_name.strip()
    try:
        p.rename(dest)
    except OSError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "path": str(dest)}


def _resolve_existing(path: str) -> tuple[Path | None, str | None]:
    p = Path((path or "").strip()).expanduser()
    try:
        p = p.absolute()
    except OSError as e:
        return None, str(e)
    if not p.exists():
        return None, "Not found."
    return p, None


def _is_protected_delete_path(p: Path) -> bool:
    """Block root and user home directory."""
    try:
        r = p.resolve()
    except OSError:
        return True
    if r == Path("/").resolve():
        return True
    try:
        if r == Path.home().resolve():
            return True
    except RuntimeError:
        pass
    return False


def delete_item(target: str) -> dict[str, Any]:
    p, err = _resolve_existing(target)
    if p is None:
        return {"ok": False, "error": err or "Invalid path."}
    if _is_protected_delete_path(p):
        return {"ok": False, "error": "This location cannot be deleted."}
    try:
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
    except OSError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True}


def delete_items(targets: list[str]) -> dict[str, Any]:
    deleted = 0
    errors: list[str] = []
    seen: set[str] = set()
    for raw in targets:
        s = (raw or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out = delete_item(s)
        if out.get("ok"):
            deleted += 1
        else:
            name = Path(s).name or s
            errors.append(f"{name}: {out.get('error', 'failed')}")
    return {
        "ok": deleted > 0 or not errors,
        "deleted": deleted,
        "failed": len(errors),
        "errors": errors[:20],
    }
