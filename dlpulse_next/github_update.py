"""GitHub release and commit checks for in-app update banners."""

from __future__ import annotations

import importlib.metadata
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GITHUB_REPO = "calvarr/DLPulse-next"
GITHUB_PROJECT_URL = f"https://github.com/{GITHUB_REPO}"
GITHUB_RELEASES_URL = f"{GITHUB_PROJECT_URL}/releases"
_API_BASE = f"https://api.github.com/repos/{GITHUB_REPO}"
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "DLPulseNext/2.0",
}
_TAG_VERSION_RE = re.compile(r"^v?(\d+(?:\.\d+)*)", re.IGNORECASE)


@dataclass(frozen=True)
class AppGitHubUpdateInfo:
    """In-app banner: newer GitHub release and/or commits on main."""

    show_banner: bool
    message: str
    kind: str  # "" | "release" | "commit"
    installed_version: str
    latest_version: str | None
    latest_tag: str | None
    releases_url: str
    release_page_url: str | None
    remote_main_sha: str | None
    dismiss_key: str | None


def _app_dir() -> Path:
    return Path(__file__).resolve().parent


def get_app_package_version() -> str:
    """PEP 621 version of the ``dlpulse-next`` distribution."""
    try:
        return importlib.metadata.version("dlpulse-next")
    except importlib.metadata.PackageNotFoundError:
        from dlpulse_next import __version__

        return __version__


def commit_page_url(full_sha: str) -> str:
    """``https://github.com/…/commit/<sha>`` for the tree this install was built from."""
    t = (full_sha or "").strip().lower()[:40]
    if len(t) < 7 or any(c not in "0123456789abcdef" for c in t):
        return GITHUB_PROJECT_URL
    return f"{GITHUB_PROJECT_URL}/commit/{t}"


def get_local_commit_sha() -> str | None:
    """SHA embedded at CI build time, or ``git rev-parse HEAD`` when developing from a clone."""
    env_raw = (os.environ.get("DLPULSE_BUILD_COMMIT") or "").strip()
    if env_raw:
        token = env_raw.split()[0]
        if len(token) >= 7 and token.lower() not in ("unknown", "none", "null"):
            if all(c in "0123456789abcdefABCDEF" for c in token[:40]):
                return token[:40].lower()

    marker = _app_dir() / "build_commit.txt"
    if marker.is_file():
        raw = marker.read_text(encoding="utf-8").strip()
        token = raw.split()[0] if raw else ""
        if len(token) >= 7 and token.lower() not in ("unknown", "none", "null"):
            return token[:40].lower()

    base = _app_dir()
    for d in (base.parent, *base.parents):
        if not (d / ".git").exists():
            continue
        try:
            r = subprocess.run(
                ["git", "-C", str(d), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if r.returncode == 0 and (sha := r.stdout.strip()):
                return sha[:40].lower()
        except (OSError, subprocess.SubprocessError):
            continue
    return None


def _http_json(url: str, timeout: float = 18.0):
    req = Request(url, headers=_HEADERS, method="GET")
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (HTTPError, URLError, OSError, json.JSONDecodeError, TypeError):
        return None


def _version_from_tag(tag_name: str) -> str | None:
    m = _TAG_VERSION_RE.match((tag_name or "").strip())
    return m.group(1) if m else None


def is_newer_version(latest: str, installed: str) -> bool:
    if not latest or not installed:
        return False
    try:
        from packaging.version import Version

        return Version(latest) > Version(installed)
    except Exception:
        return latest != installed


def _pick_stable_release(releases: list) -> dict | None:
    for item in releases:
        if not isinstance(item, dict) or item.get("draft"):
            continue
        tag = str(item.get("tag_name") or "")
        if tag.startswith("v") and _version_from_tag(tag):
            if not item.get("prerelease"):
                return item
    for item in releases:
        if not isinstance(item, dict) or item.get("draft"):
            continue
        tag = str(item.get("tag_name") or "")
        if tag.startswith("v") and _version_from_tag(tag):
            return item
    return None


def fetch_latest_github_release(timeout: float = 18.0) -> dict | None:
    """Latest stable ``v*`` release, or newest release if API ``/releases/latest`` is missing."""
    data = _http_json(f"{_API_BASE}/releases/latest", timeout=timeout)
    if isinstance(data, dict) and data.get("tag_name"):
        tag = str(data["tag_name"])
        if tag.startswith("v") and _version_from_tag(tag) and not data.get("draft"):
            return data

    items = _http_json(f"{_API_BASE}/releases?per_page=30", timeout=timeout)
    if isinstance(items, list):
        return _pick_stable_release(items)
    return None


def _branch_head_sha(branch: str = "main", timeout: float = 18.0) -> str | None:
    data = _http_json(f"{_API_BASE}/commits/{branch}", timeout=timeout)
    if not data:
        return None
    sha = (data.get("sha") or "").strip()
    return sha[:40] if len(sha) >= 7 else None


def _check_commit_behind_main(local: str, main_sha: str, timeout: float) -> AppGitHubUpdateInfo | None:
    if local.lower() == main_sha.lower():
        return None

    compare_url = f"{_API_BASE}/compare/{local}...main"
    data = _http_json(compare_url, timeout=timeout)
    installed = get_app_package_version()

    if not data:
        msg = (
            "The default branch on GitHub may be newer than this build. "
            "Open the repository or download a fresh build from Releases."
        )
        return AppGitHubUpdateInfo(
            True,
            msg,
            "commit",
            installed,
            None,
            None,
            GITHUB_RELEASES_URL,
            None,
            main_sha,
            main_sha[:40],
        )

    behind = int(data.get("behind_by") or 0)
    ahead = int(data.get("ahead_by") or 0)
    status = str(data.get("status") or "").lower()

    if status == "identical" or (behind == 0 and ahead == 0):
        return None
    if behind > 0:
        plural = "commit" if behind == 1 else "commits"
        msg = (
            f"GitHub main is {behind} {plural} ahead of this build. "
            f"Download a newer build from Releases: {GITHUB_RELEASES_URL}"
        )
        return AppGitHubUpdateInfo(
            True,
            msg,
            "commit",
            installed,
            None,
            None,
            GITHUB_RELEASES_URL,
            commit_page_url(main_sha),
            main_sha,
            main_sha[:40],
        )
    if ahead > 0 and behind == 0:
        return None

    msg = (
        f"This build and github.com/main have diverged (ahead {ahead}, behind {behind}). "
        f"See {GITHUB_RELEASES_URL}"
    )
    return AppGitHubUpdateInfo(
        True,
        msg,
        "commit",
        installed,
        None,
        None,
        GITHUB_RELEASES_URL,
        commit_page_url(main_sha),
        main_sha,
        main_sha[:40],
    )


def check_app_github_update(timeout: float = 20.0) -> AppGitHubUpdateInfo:
    """
    Prefer a newer tagged GitHub Release (``v*``) over raw commit comparison.
  Users on packaged builds should update via Releases, not git pull.
    """
    installed = get_app_package_version()
    no_banner = AppGitHubUpdateInfo(
        False,
        "",
        "",
        installed,
        None,
        None,
        GITHUB_RELEASES_URL,
        None,
        None,
        None,
    )

    release = fetch_latest_github_release(timeout=timeout)
    if release:
        tag = str(release.get("tag_name") or "")
        latest_ver = _version_from_tag(tag)
        page = str(release.get("html_url") or GITHUB_RELEASES_URL)
        if latest_ver and is_newer_version(latest_ver, installed):
            msg = (
                f"A new version is available: {tag} (you have v{installed}). "
                f"Download Linux, Windows, or macOS builds (yt-dlp, ffmpeg, aria2c included) from GitHub Releases."
            )
            return AppGitHubUpdateInfo(
                True,
                msg,
                "release",
                installed,
                latest_ver,
                tag,
                GITHUB_RELEASES_URL,
                page,
                None,
                tag,
            )

    local = get_local_commit_sha()
    if not local:
        return no_banner

    main_sha = _branch_head_sha("main", timeout=timeout)
    if not main_sha:
        return no_banner

    commit_info = _check_commit_behind_main(local, main_sha, timeout)
    if commit_info:
        return commit_info

    return AppGitHubUpdateInfo(
        False,
        "",
        "",
        installed,
        latest_ver if release else None,
        str(release.get("tag_name")) if release else None,
        GITHUB_RELEASES_URL,
        str(release.get("html_url")) if release else None,
        main_sha,
        None,
    )
