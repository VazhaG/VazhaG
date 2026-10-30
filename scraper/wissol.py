"""Wissol — the price rows (button.prices_row) on https://wissol.ge/ka/fuel-prices: the name, the standard price and,
for most fuels, a self-service price (class is-self-service), which we do not read.

Wissol's terms forbid using the site's information; the owner decided to include it anyway (SPEC-0001 §3, §7) — it is
switched off with one setting in scraper/companies.py.
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from scraper.core import PETROL, ParseError, Reading, Station, in_fuel_order, to_coordinate, to_price

URL = "https://wissol.ge/ka/fuel-prices"
STATIONS_URL = "https://wissol.ge/ka/map"

# The map page carries `const allLocations = JSON.parse('…')` — GeoJSON points ([lng, lat]) for Wissol and its sister
# companies. Wissol's own places have company_code 202161098; a fuel station is marked "სტანდარტული" or
# "თვითმომსახურება" (its petrol and diesel are not listed, so every one counts for them — SPEC-0001 REQ-003), a natural
# gas station "ბუნებრივი აირი". Service centres, the head office and payment kiosks are not stations.
_LOCATIONS_RE = re.compile(r"const allLocations = JSON\.parse\('((?:[^'\\]|\\.)*)'\)")
WISSOL_CODE = 202161098
PETROL_SERVICES = {"სტანდარტული", "თვითმომსახურება"}
CNG_SERVICE = "ბუნებრივი აირი"

# "ვისოლ გაზი": the price page does not say which gas it is; Wissol's own map marks its gas stations "ბუნებრივი აირი"
# and none as LPG, which the owner took as the confirmation SPEC-0001 REQ-002 asks for (2026-10-30).
FUEL_BY_NAME = {
    "ვისოლ გაზი": "cng",
    "A1 სუპერი 100": "super",
    "ეკო სუპერი": "super",
    "ეკო პრემიუმი": "premium",
    "ევრო რეგულარი": "regular",
    "ეკო დიზელი": "diesel",
    "ევრო დიზელი": "diesel",
    "დიზელ ენერჯი": "diesel",
}


def parse(html: str) -> list[Reading]:
    soup = BeautifulSoup(html, "html.parser")
    readings = []
    for row in soup.select("button.prices_row"):
        name = row.select_one("span p")
        standard = [p for p in row.select("p.prices_price") if "is-self-service" not in p.get("class", [])]
        if name is None or len(standard) != 1:
            raise ParseError("a price row is not the expected shape (name, standard price)")
        grade = " ".join(name.get_text(" ", strip=True).split())
        readings.append(Reading(grade, FUEL_BY_NAME.get(grade), to_price(standard[0].get_text(" ", strip=True))))
    if not readings:
        raise ParseError("no price rows")
    return readings


def parse_stations(html: str) -> list[Station]:
    m = _LOCATIONS_RE.search(html)
    if not m:
        raise ParseError("no allLocations on the map page")
    try:
        features = json.loads(json.loads('"' + m.group(1) + '"'))
        stations = []
        for f in features:
            props = f["properties"]
            if props.get("company_code") != WISSOL_CODE:
                continue
            services = {s["name"]["ka"] for s in props.get("services") or []}
            fuels = (set(PETROL) if services & PETROL_SERVICES else set()) | ({"cng"} if CNG_SERVICE in services else set())
            if fuels:
                lng, lat = f["geometry"]["coordinates"][:2]
                stations.append(Station("", " ".join(str(props.get("address") or "").split()), to_coordinate(lat),
                                        to_coordinate(lng), in_fuel_order(fuels)))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, AttributeError) as e:
        raise ParseError(f"allLocations is not the expected shape ({e!r})") from e
    return stations
