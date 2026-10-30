"""Read the companies' prices and write the data file the page reads.

    python -m scraper [--only socar,…] [--out site/data/prices.json]

A company that cannot be read keeps its previous prices, with their time (SPEC-0001 AC-005).
Exit 0 when every switched-on company's prices are younger than 48 hours. Exit 1 otherwise, so the scheduled run
turns red and GitHub tells the owner: either no company was read now (the data file is left as it was), or some
company has not been read for 48 hours (the file is written with everyone else's new prices).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from scraper.companies import COMPANIES
from scraper.core import fetch, iso, overdue, refresh

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "site" / "data" / "prices.json"


def previous_entries(path: Path) -> dict[str, dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {e["id"]: e for e in data.get("companies", []) if isinstance(e, dict) and "id" in e}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, AttributeError) as e:
        print(f"the previous data file could not be read ({e}) — starting without it", file=sys.stderr)
        return {}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m scraper")
    ap.add_argument("--only", help="comma-separated company ids; the others keep their previous prices")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    only = set(args.only.split(",")) if args.only else None
    now = datetime.now(UTC)
    entries, log, read = refresh(COMPANIES, previous_entries(args.out), fetch, now, only)
    for line in log:
        print(line, file=sys.stderr)
    for e in entries:
        print(f"{e['name']}: {len(e['prices'])} price(s), {e['time']}")
    if not read:
        print("no company was read now — the data file is unchanged", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    data = {"generated": iso(now), "companies": entries}
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if late := overdue(COMPANIES, entries, now):
        print(f"not read for 48 hours or more: {', '.join(late)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
