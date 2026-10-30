"""Lukoil Georgia — the price cards on https://www.lukoil.ge/: an image with alt "Price", then the price and the name.

A card priced 0.00 (on 2026-10-30: "Super Ecto 100") is a fuel not on sale now, not a price — it is skipped.
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from scraper.core import PETROL, ParseError, Reading, Station, to_coordinate, to_price

URL = "https://www.lukoil.ge/"
STATIONS_URL = "https://www.lukoil.ge/stations"

# The stations page draws its map with Leaflet: per station `L.marker([lat, lng])`, then `marker.bindPopup("…")` with
# the address. It names no fuels, so every station counts for petrol and diesel (SPEC-0001 REQ-003).
_MARKER_RE = re.compile(
    r'L\.marker\(\[\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\]\);\s*marker\.addTo\(mymap\);\s*'
    r'marker\.bindPopup\(("(?:[^"\\]|\\.)*")\);'
)

FUEL_BY_NAME = {
    "Super Ecto 100": "super",
    "Super Ecto": "super",
    "Premium Avangard": "premium",
    "Euro Regular": "regular",
    "Euro Diesel": "diesel",
}


def parse(html: str) -> list[Reading]:
    soup = BeautifulSoup(html, "html.parser")
    readings = []
    for img in soup.select('img[alt="Price"]'):
        card = img.find_parent("span")
        texts = [" ".join(p.get_text(" ", strip=True).split()) for p in card.find_all("p")] if card else []
        if len(texts) != 2:
            raise ParseError("a price card is not the expected shape (price, then name)")
        value, name = texts
        price = to_price(value)
        if price == 0:
            continue
        readings.append(Reading(name, FUEL_BY_NAME.get(name), price))
    if not readings:
        raise ParseError("no price cards")
    return readings


def parse_stations(html: str) -> list[Station]:
    stations = []
    for m in _MARKER_RE.finditer(html):
        try:
            address = " ".join(json.loads(m.group(3)).split())
        except json.JSONDecodeError as e:
            raise ParseError(f"a station's popup is not a string ({e!r})") from e
        stations.append(Station("", address, to_coordinate(m.group(1)), to_coordinate(m.group(2)), PETROL))
    if not stations:
        raise ParseError("no station markers")
    return stations
