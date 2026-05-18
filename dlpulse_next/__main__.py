from __future__ import annotations


def main() -> None:
    try:
        from dlpulse_next.ffmpeg_tools import apply_bundled_tool_path, find_aria2c, find_ffmpeg

        apply_bundled_tool_path()
        find_ffmpeg()
        find_aria2c()
    except Exception:
        pass
    from dlpulse_next.webapp import run_desktop

    run_desktop()


if __name__ == "__main__":
    main()
