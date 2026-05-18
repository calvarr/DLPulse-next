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


def is_media_path(path: Path | str) -> bool:
    return Path(path).suffix.lower() in MEDIA_EXTS
