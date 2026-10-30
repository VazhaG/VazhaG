"""Shared parts of the price reader: what a reading is, fetching a page, checking a reading, and one reading round.

The data file (site/data/prices.json) is what the page reads — SPEC-0001 REQ-004, REQ-006, REQ-007, AC-005.
"""

from __future__ import annotations

import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

USER_AGENT = "VazhaG-fuel-prices/0.1 (+https://github.com/VazhaG/VazhaG)"
FUELS = ("regular", "premium", "super", "diesel", "gas")

# REQ-007: a price outside these limits (GEL), or one that moved more than MAX_JUMP since the last reading of the
# same grade, is a misreading — the company's previous prices stay and the problem goes to the log.
MIN_PRICE, MAX_PRICE = 0.50, 15.00
MAX_JUMP = 0.25

_PRICE_RE = re.compile(r"\s*(\d+(?:[.,]\d+)?)\s*₾?\s*")


class ParseError(Exception):
    """The company's page no longer looks the way its reader expects."""


@dataclass(frozen=True)
class Reading:
    grade: str  # the company's own name for the fuel, e.g. "ნანო სუპერი"
    fuel: str | None  # our common type (FUELS); None when the company's name is not in its table
    price: float  # GEL


@dataclass(frozen=True)
class Company:
    id: str
    name: str
    color: str
    url: str
    parse: Callable[[str], list[Reading]]
    enabled: bool = True


def fetch(url: str, timeout: float = 30) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ka,en;q=0.8"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def to_price(text: str) -> float:
    m = _PRICE_RE.fullmatch(text)
    if not m:
        raise ParseError(f"{text.strip()!r} is not a price")
    return float(m.group(1).replace(",", "."))


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def company_entry(company: Company, readings: list[Reading], read_at: datetime) -> dict:
    """One company in the data file. `time` is when we read the page: the sites state no time of their own for
    the price list, so its age counts from our reading (SPEC-0001 REQ-006)."""
    return {
        "id": company.id,
        "name": company.name,
        "color": company.color,
        "source": company.url,
        "time": iso(read_at),
        "basis": "read",
        "prices": [{"grade": r.grade, "fuel": r.fuel, "price": r.price} for r in readings if r.fuel],
    }


def problems(readings: list[Reading], previous: dict | None) -> list[str]:
    """Why these readings cannot be true (REQ-007): a price out of limits, or a jump from the same grade's last price."""
    before = {(p.get("grade"), p.get("fuel")): p.get("price") for p in (previous or {}).get("prices", [])}
    found = []
    for r in readings:
        if not MIN_PRICE <= r.price <= MAX_PRICE:
            found.append(f"„{r.grade}“ {r.price:.2f} ₾ is outside {MIN_PRICE:.2f}–{MAX_PRICE:.2f} ₾")
            continue
        old = before.get((r.grade, r.fuel))
        if isinstance(old, (int, float)) and old > 0 and abs(r.price - old) / old > MAX_JUMP:
            found.append(f"„{r.grade}“ jumped from {old:.2f} to {r.price:.2f} ₾")
    return found


def refresh(companies: list[Company], previous: dict[str, dict], get: Callable[[str], str], now: datetime,
            only: set[str] | None = None) -> tuple[list[dict], list[str], int]:
    """One reading round: (the data file's companies, log lines, how many companies were read now).

    A company that cannot be read, or whose reading is not plausible, keeps its previous entry with its old time
    (AC-005); a switched-off company is neither read nor kept; with `only`, the others stay as they were."""
    entries: list[dict] = []
    log: list[str] = []
    read = 0
    for c in companies:
        old = previous.get(c.id)
        if not c.enabled:
            log.append(f"{c.name}: switched off — not read, its prices removed")
            continue
        if only is not None and c.id not in only:
            if old:
                entries.append(old)
            continue
        try:
            readings = c.parse(get(c.url))
            known = [r for r in readings if r.fuel]
            if not known:
                raise ParseError("no price matched the fuel table")
            if found := problems(known, old):
                raise ParseError("; ".join(found))
        except (OSError, ParseError) as e:
            log.append(f"{c.name}: not read — {e}" + (" (the previous prices stay, with their time)" if old else ""))
            if old:
                entries.append(old)
            continue
        log.extend(f"{c.name}: „{r.grade}“ is not in the fuel table — left out" for r in readings if not r.fuel)
        entries.append(company_entry(c, readings, now))
        read += 1
    return entries, log, read
