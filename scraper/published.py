"""Where the scheduled run starts: the data the site publishes now, whose times are the last good readings.

    python -m scraper.published https://vazhag.github.io/VazhaG/data/ site/data/prices.json site/data/stations.json

Each published file is written over the repository's copy. That copy is committed only when prices change
(scraper/changed.py), so its times can be weeks old: starting from it would hide prices read hours ago and turn their
companies overdue (SPEC-0001 REQ-006, REQ-007). It stays the start only when the site has no such file yet (404,
before the first publication) or the published one cannot be taken (not a data file, larger than the reader takes),
so that one broken file cannot stop every run after it. Any other failure, after TRIES tries, exits 1: nothing is read
or published in that run.
"""

from __future__ import annotations

import http.client
import json
import sys
import time
import urllib.error
from collections.abc import Callable
from pathlib import Path

from scraper.core import ParseError, fetch, one_line

TRIES = 3
WAIT_S = 5.0
FAILURES = (OSError, http.client.HTTPException)  # a connection cut mid-file is http.client's, not an OSError


def _get(url: str, get: Callable[[str], str]) -> str | None:
    try:
        return get(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def download(url: str, get: Callable[[str], str], wait: Callable[[float], None]) -> str | None:
    """The published text, or None when the site has no such file (404)."""
    for _ in range(TRIES - 1):
        try:
            return _get(url, get)
        except FAILURES:
            wait(WAIT_S)
    return _get(url, get)


def is_data(text: str) -> bool:
    try:
        data = json.loads(text)
    except ValueError:
        return False
    return isinstance(data, dict) and isinstance(data.get("companies"), list)


def start(base: str, paths: list[Path], get: Callable[[str], str], wait: Callable[[float], None]) -> list[str]:
    """Write each published file over the repository's copy; the lines say where each one starts from."""
    log = []
    for path in paths:
        try:
            text = download(base + path.name, get, wait)
        except ParseError as e:  # e.g. larger than the reader takes: the same file would come again on every try
            log.append(f"::warning::the published {path.name} could not be taken ({e}) — starting from the repository's")
            continue
        if text is None:
            log.append(f"no published {path.name} yet — starting from the repository's")
        elif not is_data(text):
            log.append(f"::warning::the published {path.name} is not a data file — starting from the repository's")
        else:
            path.write_text(text, encoding="utf-8")
            log.append(f"{path.name}: starting from the published file")
    return log


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    base, *files = argv if argv is not None else sys.argv[1:]
    try:
        log = start(base, [Path(f) for f in files], fetch, time.sleep)
    except FAILURES as e:
        print(one_line(f"::error::the published data could not be read ({type(e).__name__}: {e}) — nothing is read or "
                       "published in this run"))
        return 1
    print("\n".join(log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
