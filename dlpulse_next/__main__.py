from __future__ import annotations

import sys


def main() -> None:
    from dlpulse_next.packaged_runtime import (
        apply_windows_packaged_env,
        report_fatal_error,
        setup_packaged_logging,
    )

    apply_windows_packaged_env()
    setup_packaged_logging()

    try:
        try:
            from dlpulse_next.ffmpeg_tools import apply_bundled_tool_path, find_aria2c, find_ffmpeg

            apply_bundled_tool_path()
            find_ffmpeg()
            find_aria2c()
        except Exception:
            pass
        from dlpulse_next.webapp import run_desktop

        run_desktop()
    except Exception as exc:
        report_fatal_error(exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
