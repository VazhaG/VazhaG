"""Shared parts of the price reader: what a reading and a station are, fetching a page, checking what was read, and
one reading round.

The data files (site/data/prices.json, site/data/stations.json) are what the page reads — SPEC-0001 REQ-001,
REQ-003, REQ-004, REQ-006, REQ-007, AC-002, AC-005.
"""

from __future__ import annotations

import math
import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

USER_AGENT = "VazhaG-fuel-prices/0.1 (+https://github.com/VazhaG/VazhaG)"
# REQ-002: the two gases are separate types, never compared (the owner's decision, 2026-10-30)
FUELS = ("regular", "premium", "super", "diesel", "lpg", "cng")
# REQ-003: when a station list does not say which of these a station sells, every station of the company counts for
# them (the owner's decision, 2026-10-30); a gas is never assumed.
PETROL = ("regular", "premium", "super", "diesel")

# REQ-007: a price outside these limits (GEL), or one that moved more than MAX_JUMP from the same grade's previous
# price (only a previous price younger than JUMP_WINDOW counts), is a misreading — the company's previous prices stay
# and the problem goes to the log. A company whose prices are OVERDUE_AFTER old makes the run fail, so GitHub tells
# the owner.
MIN_PRICE, MAX_PRICE = 0.50, 15.00
MAX_JUMP = 0.25
JUMP_WINDOW = timedelta(days=7)
OVERDUE_AFTER = timedelta(hours=48)

# AC-002: a station whose place is not inside this box around Georgia (latitude, longitude) is not shown. A station
# list less than half as long as the last one is a misreading, like an implausible price.
LAT_RANGE, LNG_RANGE = (41.0, 43.7), (39.9, 46.8)
MIN_SHARE = 0.5

_PRICE_RE = re.compile(r"\s*(\d+(?:[.,]\d+)?)\s*₾?\s*")


class ParseError(Exception):
    """The company's page no longer looks the way its reader expects."""


@dataclass(frozen=True)
class Reading:
    grade: str  # the company's own name for the fuel, e.g. "ნანო სუპერი"
    fuel: str | None  # our common type (FUELS); None when the company's name is not in its table
    price: float  # GEL


@dataclass(frozen=True)
class Station:
    name: str  # "" when the company's list gives none
    address: str
    lat: float | None  # None when the list gives no usable place
    lng: float | None
    fuels: tuple[str, ...]  # our types, in FUELS order: what the list says, or PETROL where it says nothing


@dataclass(frozen=True)
class Company:
    id: str
    name: str
    color: str
    url: str
    parse: Callable[[str], list[Reading]]
    enabled: bool = True
    stations_url: str = ""
    parse_stations: Callable[[str], list[Station]] | None = None


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


def to_coordinate(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None  # NaN and infinity are not places


def in_fuel_order(fuels: set[str]) -> tuple[str, ...]:
    return tuple(f for f in FUELS if f in fuels)


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(text: object) -> datetime | None:
    try:
        moment = datetime.fromisoformat(text)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo else None


def _entry(company: Company, source: str, read_at: datetime, key: str, items: list[dict]) -> dict:
    """One company in a data file. `time` is when we read the source: the sites state no time of their own, so the
    age counts from our reading (SPEC-0001 REQ-006)."""
    return {"id": company.id, "name": company.name, "color": company.color, "source": source,
            "time": iso(read_at), "basis": "read", key: items}


def company_entry(company: Company, readings: list[Reading], read_at: datetime) -> dict:
    prices = [{"grade": r.grade, "fuel": r.fuel, "price": r.price} for r in readings if r.fuel]
    return _entry(company, company.url, read_at, "prices", prices)


def problems(readings: list[Reading], previous: dict | None, now: datetime) -> list[str]:
    """Why these readings cannot be true (REQ-007): a price out of limits, or a jump from the same grade's previous
    price when that price is younger than JUMP_WINDOW."""
    then = parse_time((previous or {}).get("time"))
    before = {}
    if then is not None and now - then < JUMP_WINDOW:
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


def placed(station: Station) -> bool:
    return (station.lat is not None and station.lng is not None
            and LAT_RANGE[0] <= station.lat <= LAT_RANGE[1] and LNG_RANGE[0] <= station.lng <= LNG_RANGE[1])


def _round(companies: list[Company], previous: dict[str, dict], only: set[str] | None, what: str,
           read: Callable[[Company, dict | None], tuple[dict, list[str]]]) -> tuple[list[dict], list[str], int]:
    """One reading round over the companies: (the data file's companies, log lines, how many were read now).

    A company that cannot be read, or whose reading is not plausible, keeps its previous entry with its old time
    (AC-005); a switched-off company is neither read nor kept; with `only`, the others stay as they were."""
    entries: list[dict] = []
    log: list[str] = []
    done = 0
    label = "" if what == "prices" else f"{what} "
    for c in companies:
        old = previous.get(c.id)
        if not c.enabled:
            log.append(f"{c.name}: switched off — not read, its {what} removed")
            continue
        if only is not None and c.id not in only:
            if old:
                entries.append(old)
            continue
        try:
            entry, notes = read(c, old)
        except (OSError, ParseError) as e:
            stay = f" (the previous {what} stay, with their time)" if old else ""
            log.append(f"{c.name}: {label}not read — {e}{stay}")
            if old:
                entries.append(old)
            continue
        log.extend(notes)
        entries.append(entry)
        done += 1
    return entries, log, done


def refresh(companies: list[Company], previous: dict[str, dict], get: Callable[[str], str], now: datetime,
            only: set[str] | None = None) -> tuple[list[dict], list[str], int]:
    """The prices round (REQ-006, REQ-007)."""

    def read(c: Company, old: dict | None) -> tuple[dict, list[str]]:
        readings = c.parse(get(c.url))
        known = [r for r in readings if r.fuel]
        if not known:
            raise ParseError("no price matched the fuel table")
        if found := problems(known, old, now):
            raise ParseError("; ".join(found))
        notes = [f"{c.name}: „{r.grade}“ is not in the fuel table — left out" for r in readings if not r.fuel]
        return company_entry(c, readings, now), notes

    return _round(companies, previous, only, "prices", read)


def refresh_stations(companies: list[Company], previous: dict[str, dict], get: Callable[[str], str], now: datetime,
                     only: set[str] | None = None) -> tuple[list[dict], list[str], int]:
    """The stations round (REQ-001, REQ-003, AC-002): stations without a place in Georgia are left out; a list less
    than half as long as the previous one is a misreading."""

    def read(c: Company, old: dict | None) -> tuple[dict, list[str]]:
        if c.parse_stations is None:
            raise ParseError("no station list for this company")
        stations = c.parse_stations(get(c.stations_url))
        kept = [s for s in stations if placed(s)]
        before = len((old or {}).get("stations", []))
        if not kept:
            raise ParseError("no station with a place in Georgia")
        if len(kept) < before * MIN_SHARE:
            raise ParseError(f"only {len(kept)} station(s), the last list had {before}")
        dropped = len(stations) - len(kept)
        notes = [f"{c.name}: {dropped} station(s) without a place in Georgia — left out"] if dropped else []
        items = [{"name": s.name, "address": s.address, "lat": s.lat, "lng": s.lng, "fuels": list(s.fuels)}
                 for s in kept]
        return _entry(c, c.stations_url, now, "stations", items), notes

    return _round([c for c in companies if c.parse_stations is not None], previous, only, "stations", read)


def overdue(companies: list[Company], entries: list[dict], now: datetime) -> list[str]:
    """Switched-on companies whose prices are OVERDUE_AFTER old or missing — the run fails for them (REQ-007)."""
    times = {e.get("id"): parse_time(e.get("time")) for e in entries}
    late = []
    for c in companies:
        then = times.get(c.id)
        if c.enabled and (then is None or now - then >= OVERDUE_AFTER):
            late.append(c.name)
    return late
