import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import time
from datetime import datetime, timedelta

from .agent import AutoPlayAgent


def _wait_until(hhmm: str) -> None:
    target = datetime.strptime(hhmm, "%H:%M").replace(
        year=datetime.now().year,
        month=datetime.now().month,
        day=datetime.now().day,
    )
    if target <= datetime.now():
        target += timedelta(days=1)
    seconds = (target - datetime.now()).total_seconds()
    print(f"Scheduled for {target.strftime('%Y-%m-%d %H:%M')} — waiting {seconds/3600:.1f}h")
    time.sleep(seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto Play Agent")
    parser.add_argument(
        "--at",
        metavar="HH:MM",
        help="Start at this time today (24h). If already past, runs tomorrow.",
    )
    args = parser.parse_args()

    if args.at:
        _wait_until(args.at)

    AutoPlayAgent().run()


if __name__ == "__main__":
    main()
