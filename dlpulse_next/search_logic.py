"""
Search / URL resolution — mirrors ``flet_app/main.py`` flow (``_resolve_url``, ``_search_keywords``).
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

from dlpulse_next.yt_core import (
    detect_content_type,
    extract_url_info,
    fetch_playlist_entries,
    get_format_preset,
    normalize_youtube_radio_mix_url,
    search_keywords_multi,
)


def input_looks_like_url(s: str) -> bool:
    t = s.strip()
    if not t:
        return False
    tl = t.lower()
    if tl.startswith(("http://", "https://")):
        return True
    if "youtube.com" in tl or "youtu.be" in tl:
        return True
    return False


def thumbnail_from_extract_info(info: dict) -> str:
    t = (info.get("thumbnail") or "").strip()
    if t:
        return t
    thumbs = info.get("thumbnails") or []
    if isinstance(thumbs, list) and thumbs:
        last = thumbs[-1]
        if isinstance(last, dict):
            u = (last.get("url") or "").strip()
            if u:
                return u
    vid = info.get("id") or ""
    if isinstance(vid, str) and len(vid) == 11 and not vid.startswith("UC"):
        return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    return ""


def search_hit_from_extract_info(info: dict, page_url: str) -> dict[str, Any]:
    """Same shape as ``search_youtube`` rows: id, title, url, thumbnail."""
    thumb = thumbnail_from_extract_info(info)
    vid = info.get("id") or ""
    if not thumb and isinstance(vid, str) and len(vid) == 11:
        thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    title = (info.get("title") or "").strip() or "Untitled"
    return {"id": vid, "title": title, "url": page_url, "thumbnail": thumb}


def display_title_for_row(item: dict, *, kind: str, sources_used: Collection[str]) -> str:
    """``[YT]`` / ``[SC]`` prefixes when both engines were used (Flet ``_result_row_display_title``)."""
    raw_title = (item.get("title") or "").strip()
    src = (item.get("source") or "").strip().lower()
    su = set(sources_used)
    if kind == "search" and len(su) > 1 and src == "soundcloud":
        disp = f"[SC] {raw_title}" if raw_title else ""
    elif kind == "search" and len(su) > 1 and src == "youtube":
        disp = f"[YT] {raw_title}" if raw_title else ""
    else:
        disp = raw_title
    return (disp or "Untitled").replace("\n", " ")[:240]


def preset_requires_ffmpeg_conversion(fmt_i: int) -> bool:
    """True for presets that need FFmpeg re-encode/extract (e.g. MP3/M4A)."""
    preset = get_format_preset(fmt_i)
    if not preset:
        return False
    _spec, extra = preset
    post = extra.get("postprocessors") or []
    if not isinstance(post, list):
        return False
    for p in post:
        if isinstance(p, dict) and str(p.get("key", "")).strip() == "FFmpegExtractAudio":
            return True
    return False


def enrich_items_with_display_titles(
    items: list[dict], *, result_kind: str, sources_used: Collection[str]
) -> list[dict]:
    su = frozenset(sources_used) if result_kind == "search" else frozenset()
    out: list[dict] = []
    for it in items:
        row = dict(it)
        row["title_display"] = display_title_for_row(it, kind=result_kind, sources_used=su)
        out.append(row)
    return out


def resolve_search_or_url(
    text: str,
    *,
    youtube: bool = True,
    soundcloud: bool = False,
    max_per_source: int = 12,
) -> dict[str, Any]:
    """
    Returns JSON-serializable dict:
    - ok: bool
    - kind: ``search`` | ``playlist`` | ``empty`` | ``error``
    - items: list of row dicts (id, title, url, thumbnail, optional source)
    - sources_used: list[str] (keyword search only)
    - message: str (status line for UI)
    - error: str if ok is False
    """
    q = (text or "").strip()
    if not q:
        return {
            "ok": True,
            "kind": "empty",
            "items": [],
            "sources_used": [],
            "message": "Enter search words or a URL.",
        }

    if input_looks_like_url(q):
        raw = q
        probe = raw.replace("music.youtube.com", "www.youtube.com", 1) if "music.youtube.com" in raw else raw

        entries, err = fetch_playlist_entries(probe, 500, normalize_url=False)
        if err:
            return {"ok": False, "kind": "error", "error": err[:300], "items": [], "sources_used": []}
        if entries:
            items = enrich_items_with_display_titles(entries, result_kind="playlist", sources_used=[])
            return {
                "ok": True,
                "kind": "playlist",
                "items": items,
                "sources_used": [],
                "message": f"{len(entries)} videos.",
            }

        canonical = normalize_youtube_radio_mix_url(probe)
        info = extract_url_info(canonical)
        if not info:
            return {
                "ok": False,
                "kind": "error",
                "error": "URL unreachable or blocked.",
                "items": [],
                "sources_used": [],
            }

        ctype, _desc = detect_content_type(info)
        if ctype in ("playlist", "channel"):
            entries2, err2 = fetch_playlist_entries(canonical, 500)
            if err2:
                return {"ok": False, "kind": "error", "error": err2[:300], "items": [], "sources_used": []}
            items = enrich_items_with_display_titles(entries2, result_kind="playlist", sources_used=[])
            return {
                "ok": True,
                "kind": "playlist",
                "items": items,
                "sources_used": [],
                "message": f"{len(entries2)} videos.",
            }

        hit = search_hit_from_extract_info(info, canonical)
        items = enrich_items_with_display_titles([hit], result_kind="search", sources_used=[])
        return {
            "ok": True,
            "kind": "search",
            "items": items,
            "sources_used": [],
            "message": "",
        }

    if not youtube and not soundcloud:
        return {
            "ok": False,
            "kind": "error",
            "error": "Select at least one search source: YouTube and/or SoundCloud.",
            "items": [],
            "sources_used": [],
        }

    hits, used = search_keywords_multi(
        q,
        youtube=youtube,
        soundcloud=soundcloud,
        max_per_source=max_per_source,
    )
    parts = [p for p, ok in (("YouTube", youtube), ("SoundCloud", soundcloud)) if ok]
    busy_lbl = " + ".join(parts)
    used_list = list(used)
    items = enrich_items_with_display_titles(hits, result_kind="search", sources_used=used_list)
    return {
        "ok": True,
        "kind": "search",
        "items": items,
        "sources_used": used_list,
        "message": f"{len(hits)} results ({busy_lbl}).",
    }
