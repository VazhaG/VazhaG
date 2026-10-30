"""Read the companies' prices and stations and write the data files the page reads.

    python -m scraper [--only socar,…] [--out site/data/prices.json] [--stations-out site/data/stations.json]

A company that cannot be read keeps its previous prices or stations, with their time (SPEC-0001 AC-005).
Exit 0 when every switched-on company's prices and stations are younger than 48 hours. Exit 1 otherwise, so the
scheduled run turns red and GitHub tells the owner: either no company's prices were read now (the prices file is left
as it was), or some company's prices or stations have not been read for 48 hours (the files are written with
everyone else's new data).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from scraper.companies import COMPANIES
from scraper.core import fetch, iso, one_line, overdue, refresh, refresh_stations

DATA = Path(__file__).resolve().parent.parent / "site" / "data"
DEFAULT_OUT = DATA / "prices.json"
DEFAULT_STATIONS_OUT = DATA / "stations.json"


def previous_entries(path: Path) -> dict[str, dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {e["id"]: e for e in data.get("companies", []) if isinstance(e, dict) and "id" in e}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, AttributeError) as e:
        say(f"the previous data file {path.name} could not be read ({e}) — starting without it")
        return {}


def write(path: Path, entries: list[dict], now: datetime) -> None:
    """Encoded before anything is written, and swapped in whole: a file that cannot be written stays as it was."""
    data = json.dumps({"generated": iso(now), "companies": entries}, ensure_ascii=False, indent=2) + "\n"
    body = data.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    try:
        part.write_bytes(body)
        os.replace(part, path)
    finally:
        part.unlink(missing_ok=True)  # a half-written part must not be published with the site


def say(line: str) -> None:
    print(one_line(line), file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")  # text from a source never stops the run
    ap = argparse.ArgumentParser(prog="python -m scraper")
    ap.add_argument("--only", help="comma-separated company ids; the others keep what they had")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--stations-out", type=Path, default=DEFAULT_STATIONS_OUT)
    args = ap.parse_args(argv)
    only = set(args.only.split(",")) if args.only else None
    now = datetime.now(UTC)
    entries, log, read = refresh(COMPANIES, previous_entries(args.out), fetch, now, only)
    places, places_log, places_read = refresh_stations(COMPANIES, previous_entries(args.stations_out), fetch, now, only)
    for line in log + places_log:
        say(line)
    for e in entries:
        print(one_line(f"{e['name']}: {len(e['prices'])} price(s), {e['time']}"))
    for e in places:
        print(one_line(f"{e['name']}: {len(e['stations'])} station(s), {e['time']}"))
    if places_read:
        write(args.stations_out, places, now)
    else:
        say("no station list was read now — the stations file is unchanged")
    if not read:
        say("no company's prices were read now — the prices file is unchanged")
        return 1
    write(args.out, entries, now)
    status = 0
    if late := overdue(COMPANIES, entries, now):
        say(f"prices not read for 48 hours or more: {', '.join(late)}")
        status = 1
    if late := overdue([c for c in COMPANIES if c.parse_stations is not None], places, now):
        say(f"stations not read for 48 hours or more: {', '.join(late)}")
        status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
