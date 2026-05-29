from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from dlpulse_next.media_paths import find_cover_for_media, is_media_path


def library_row_subtitle(st: os.stat_result) -> str:
    """Size in MB plus creation time (Windows); else birth time or last modified."""
    mb = max(0, st.st_size) / (1024.0 * 1024.0)
    size_s = f"{mb:.2f} MB"
    birth = getattr(st, "st_birthtime", None)
    if birth is not None:
        label, ts = "Created", float(birth)
    elif os.name == "nt":
        label, ts = "Created", float(st.st_ctime)
    else:
        label, ts = "Modified", float(st.st_mtime)
    try:
        when = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError):
        when = "—"
    return f"{size_s} · {label}: {when}"


def scan_library(
    downloads_dir: Path,
    *,
    session_dir: Path | None = None,
    view_dir: Path | None = None,
    max_items: int = 800,
    media_only: bool = True,
) -> list[dict[str, Any]]:
    """
    Returns API-ready rows (newest first by mtime), deduped by resolved path.

    Only **immediate** files in each root directory are listed (no recursive walk).
    Default view uses the save folder from Settings only; ``session_dir`` is ignored
    for listing so the library stays fast on large trees.
    """
    _ = session_dir  # API compatibility; listing is save/browse folder only
    roots: list[Path] = []
    if view_dir is not None:
        try:
            r = view_dir.expanduser().resolve()
        except OSError:
            r = view_dir.expanduser()
        roots.append(r)
        multi = False
    else:
        try:
            r0 = downloads_dir.expanduser().resolve()
        except OSError:
            r0 = downloads_dir.expanduser()
        roots.append(r0)
        multi = False

    # (mtime, label, path, stat_result | None)
    all_files: list[tuple[float, str, Path, os.stat_result | None]] = []

    for root in roots:
        if not root.is_dir():
            continue
        try:
            root_r = root.expanduser().resolve()
        except OSError:
            root_r = root.expanduser()
        anchor = root.name or root_r.as_posix().rstrip("/").split("/")[-1] or "folder"
        try:
            with os.scandir(root_r) as it:
                for entry in it:
                    try:
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        p = Path(entry.path)
                        if media_only and not is_media_path(p):
                            continue
                        try:
                            rel = p.relative_to(root_r)
                        except ValueError:
                            continue
                        rel_s = rel.as_posix()
                        label = f"{anchor}/{rel_s}" if multi else rel_s
                        try:
                            st = entry.stat(follow_symlinks=False)
                            mtime = float(st.st_mtime)
                        except OSError:
                            st = None
                            mtime = 0.0
                        all_files.append((mtime, label, p, st))
                    except OSError:
                        continue
        except OSError:
            continue

    by_key: dict[Path, tuple[float, str, Path, os.stat_result | None]] = {}
    for mtime, label, p, st in all_files:
        try:
            key = p.resolve()
        except OSError:
            key = p
        prev = by_key.get(key)
        if prev is None or mtime > prev[0]:
            by_key[key] = (mtime, label, p, st)

    merged = sorted(by_key.values(), key=lambda t: t[0], reverse=True)
    out: list[dict[str, Any]] = []
    for _mt, label, p, st in merged[:max_items]:
        if st is not None:
            try:
                sub = library_row_subtitle(st)
            except OSError:
                sub = "—"
        else:
            sub = "—"
        try:
            abs_s = str(p.resolve())
        except OSError:
            abs_s = str(p)
        row: dict[str, Any] = {"label": label[:200], "path": abs_s, "subtitle": sub}
        cov = find_cover_for_media(p)
        if cov is not None:
            row["cover_url"] = f"/api/library/cover?path={quote(abs_s, safe='')}"
        out.append(row)
    return out
