"""Read the companies' prices and write the data file the page reads.

    python -m scraper [--only socar,…] [--out site/data/prices.json]

Exit 0 when at least one company was read, 1 when none was.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from scraper.companies import COMPANIES
from scraper.core import ParseError, company_entry, fetch, iso

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "site" / "data" / "prices.json"


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="python -m scraper")
    ap.add_argument("--only", help="comma-separated company ids")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    wanted = set(args.only.split(",")) if args.only else None
    now = datetime.now(UTC)
    entries = []
    for company in COMPANIES:
        if wanted is not None and company.id not in wanted:
            continue
        try:
            readings = company.parse(fetch(company.url))
        except (OSError, ParseError) as e:
            print(f"{company.name}: not read — {e}", file=sys.stderr)
            continue
        for r in readings:
            if r.fuel is None:
                print(f"{company.name}: „{r.grade}“ is not in the fuel table — left out", file=sys.stderr)
        entries.append(company_entry(company, readings, now))
        print(f"{company.name}: {sum(1 for r in readings if r.fuel)} price(s)")
    if not entries:
        print("no company was read — the data file is unchanged", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    data = {"generated": iso(now), "companies": entries}
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
