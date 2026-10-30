"""Shared parts of the price reader: what a reading is, fetching a page, and one company's entry in the data file.

The data file (site/data/prices.json) is what the page reads — SPEC-0001 REQ-004, REQ-006.
"""

from __future__ import annotations

import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

USER_AGENT = "VazhaG-fuel-prices/0.1 (+https://github.com/VazhaG/VazhaG)"
FUELS = ("regular", "premium", "super", "diesel", "gas")


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


def fetch(url: str, timeout: float = 30) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ka,en;q=0.8"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


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
