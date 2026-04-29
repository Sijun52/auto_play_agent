import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from .agent import AutoPlayAgent


def main() -> None:
    AutoPlayAgent().run()


if __name__ == "__main__":
    main()
