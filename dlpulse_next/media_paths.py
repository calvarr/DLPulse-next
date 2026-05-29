"""Audio/video extensions for library and folder browser listings."""

from __future__ import annotations

from pathlib import Path

AUDIO_EXTS = frozenset(
    {
        ".mp3",
        ".m4a",
        ".aac",
        ".flac",
        ".ogg",
        ".opus",
        ".wav",
        ".wma",
        ".m4b",
        ".alac",
        ".aiff",
        ".aif",
        ".ape",
        ".wv",
    }
)

VIDEO_EXTS = frozenset(
    {
        ".mp4",
        ".webm",
        ".mkv",
        ".avi",
        ".mov",
        ".wmv",
        ".flv",
        ".m4v",
        ".mpeg",
        ".mpg",
        ".3gp",
        ".ogv",
        ".ts",
        ".m2ts",
    }
)

MEDIA_EXTS = AUDIO_EXTS | VIDEO_EXTS

COVER_EXTS = frozenset({".jpg", ".jpeg", ".webp", ".png"})


def is_media_path(path: Path | str) -> bool:
    return Path(path).suffix.lower() in MEDIA_EXTS


def is_cover_path(path: Path | str) -> bool:
    return Path(path).suffix.lower() in COVER_EXTS


def find_cover_for_media(media_path: Path | str) -> Path | None:
    """
    Sidecar artwork next to a media file (``track.mp3`` + ``track.webp`` / ``track.jpg``).
    yt-dlp ``writethumbnail`` often writes ``Title.webp`` beside ``Title.mp3``.
    """
    p = Path(media_path).expanduser()
    if not p.is_file():
        return None
    stem = p.stem
    parent = p.parent
    for ext in (".webp", ".jpg", ".jpeg", ".png"):
        candidate = parent / f"{stem}{ext}"
        try:
            if candidate.is_file() and candidate.resolve() != p.resolve():
                return candidate
        except OSError:
            if candidate.is_file():
                return candidate
    return None


def cover_mimetype(path: Path | str) -> str:
    suf = Path(path).suffix.lower()
    if suf in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suf == ".webp":
        return "image/webp"
    if suf == ".png":
        return "image/png"
    return "application/octet-stream"
