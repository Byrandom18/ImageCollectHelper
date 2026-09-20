from __future__ import annotations

import sys


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main() -> None:
    _configure_stdio()
    if len(sys.argv) > 1 and sys.argv[1] in {"--cli", "cli"}:
        from collector.cli import run_cli

        raise SystemExit(run_cli(sys.argv[2:]))
    from collector.gui import run_gui

    run_gui()


if __name__ == "__main__":
    main()
