"""Connect („ქონექთი“) — the price block (div#fpc…) on https://connect.com.ge/: one card per fuel, with its name and
two prices labelled „სტანდარტული“ (class fpc-feat-std / fpc-pstd) and „თვითმომსახურება“ (fpc-feat-self / fpc-pself).
The standard price is read by its class, never by its place: the two swap places between cards (on 2026-10-31 the
first card lists self-service first). The self-service price is not read, as for the other companies.

The stations come from the list Connect's map page loads (WordPress's Agile Store Locator): the map page hands its
visitors a short-lived code, and the list is asked for with it — two requests, as the page's own script makes them.

Connect's terms forbid spreading the site's content without written consent; the owner decided to include it anyway
(SPEC-0003 REQ-004) — it is switched off with one setting in scraper/companies.py.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from collections.abc import Callable

from bs4 import BeautifulSoup

from scraper.core import PETROL, ParseError, Reading, Station, to_coordinate, to_price

URL = "https://connect.com.ge/"
MAP_URL = "https://connect.com.ge/map/"
LIST_URL = "https://connect.com.ge/wp-admin/admin-ajax.php"

# REQ-006: the addresses above are fixed; only the code passes from the map page into a request, and only in the shape
# such a code has — anything else (another character, another length) is no code. The page's own `ajax_url` is not
# followed.
_CODE_RE = re.compile(r'ASL_REMOTE\s*=\s*\{[^{}]*?"nonce"\s*:\s*"([0-9A-Za-z]{6,32})"')

FUEL_BY_NAME = {
    "სუპერი RON 98": "super",
    "პრემიუმი RON 96": "premium",
    "რეგულარი RON 93": "regular",
    "ევრო დიზელი 10PPM": "diesel",
    "დიზელი 10PPM": "diesel",
}


def parse(html: str) -> list[Reading]:
    soup = BeautifulSoup(html, "html.parser")
    readings = []
    for card in soup.select(".fpc-featured, .fpc-card"):
        name = card.select_one(".fpc-feat-name, .fpc-card-name")
        standard = card.select(".fpc-feat-std, .fpc-pstd")
        if name is None or len(standard) != 1:
            raise ParseError("a price card is not the expected shape (name, one standard price)")
        grade = " ".join(name.get_text(" ", strip=True).split())
        readings.append(Reading(grade, FUEL_BY_NAME.get(grade), to_price(standard[0].get_text(" ", strip=True))))
    if not readings:
        raise ParseError("no price cards")
    return readings


def stations_text(get: Callable[[str], str]) -> str:
    """The station list's text: the map page first, for its code, then the list at its fixed address with that code
    (REQ-002, REQ-006)."""
    m = _CODE_RE.search(get(MAP_URL))
    if not m:
        raise ParseError("no code for the station list on the map page")
    query = urllib.parse.urlencode({"action": "asl_load_stores", "nonce": m.group(1), "asl_lang": "", "load_all": "1",
                                    "layout": "0"})
    return get(f"{LIST_URL}?{query}")


def parse_stations(text: str) -> list[Station]:
    """One station per record: the town or village as its name, `street` as its address (`city` when it is empty).
    The list names no fuels, so every station counts for petrol and diesel (SPEC-0001 REQ-003)."""
    try:
        records = json.loads(text)
    except json.JSONDecodeError as e:
        raise ParseError(f"the station list is not JSON ({e!r})") from e
    if not isinstance(records, list):
        raise ParseError("the station list is not a list")
    stations = []
    for r in records:
        if not isinstance(r, dict):
            raise ParseError("a station is not the expected shape (an object)")
        street, city = (" ".join(str(r.get(k) or "").split()) for k in ("street", "city"))
        stations.append(Station(" ".join(str(r.get("title") or "").split()), street or city,
                                to_coordinate(r.get("lat")), to_coordinate(r.get("lng")), PETROL))
    return stations
