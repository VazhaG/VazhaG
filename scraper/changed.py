"""Should the scheduled run commit the data files? Prints `changed=true` or `changed=false` (for $GITHUB_OUTPUT).

    python -m scraper.changed site/data/prices.json site/data/stations.json

True when a file's prices or stations differ from the last commit's — the reading times aside, since they change on
every run and the published site carries them anyway — or when the branch has had no commit for KEEPALIVE: GitHub
switches a public repository's schedule off after 60 days without activity (ADR-0012).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

KEEPALIVE = timedelta(days=30)


def comparable(text: str | None) -> object:
    """The data without its times: `generated` and every company's `time`."""
    if text is None:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return text
    if isinstance(data, dict):
        data.pop("generated", None)
        for company in data.get("companies", []):
            if isinstance(company, dict):
                company.pop("time", None)
    return data


def changed(paths: list[Path], committed: Callable[[Path], str | None], last_commit: float | None,
            now: float) -> tuple[bool, str]:
    for path in paths:
        if comparable(path.read_text(encoding="utf-8")) != comparable(committed(path)):
            return True, f"{path.name} changed"
    if last_commit is None or now - last_commit >= KEEPALIVE.total_seconds():
        return True, f"no commit for {KEEPALIVE.days} days — keeping the schedule alive"
    return False, "prices and stations as committed"


def _git(*args: str) -> str | None:
    r = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", check=False)
    return r.stdout if r.returncode == 0 else None


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    paths = [Path(p) for p in (argv if argv is not None else sys.argv[1:])]
    stamp = _git("log", "-1", "--format=%ct", "HEAD")
    is_changed, why = changed(paths, lambda p: _git("show", f"HEAD:{p.as_posix()}"),
                              float(stamp) if stamp and stamp.strip() else None, time.time())
    print(why, file=sys.stderr)
    print(f"changed={'true' if is_changed else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
