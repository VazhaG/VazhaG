"""Read the companies' prices and stations and write the data files the page reads.

    python -m scraper [--only socar,…] [--out site/data/prices.json] [--stations-out site/data/stations.json]

A company that cannot be read keeps its previous prices or stations, with their time (SPEC-0001 AC-005).
Exit 0 when every switched-on company's prices are younger than 48 hours. Exit 1 otherwise, so the scheduled run
turns red and GitHub tells the owner: either no company's prices were read now (the prices file is left as it was),
or some company has not been read for 48 hours (the file is written with everyone else's new prices). A station list
that cannot be read keeps the previous one and shows in the log; it does not change the exit code.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from scraper.companies import COMPANIES
from scraper.core import fetch, iso, overdue, refresh, refresh_stations

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
        print(f"the previous data file {path.name} could not be read ({e}) — starting without it", file=sys.stderr)
        return {}


def write(path: Path, entries: list[dict], now: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"generated": iso(now), "companies": entries}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
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
        print(line, file=sys.stderr)
    for e in entries:
        print(f"{e['name']}: {len(e['prices'])} price(s), {e['time']}")
    for e in places:
        print(f"{e['name']}: {len(e['stations'])} station(s), {e['time']}")
    if places_read:
        write(args.stations_out, places, now)
    else:
        print("no station list was read now — the stations file is unchanged", file=sys.stderr)
    if not read:
        print("no company's prices were read now — the prices file is unchanged", file=sys.stderr)
        return 1
    write(args.out, entries, now)
    if late := overdue(COMPANIES, entries, now):
        print(f"prices not read for 48 hours or more: {', '.join(late)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
