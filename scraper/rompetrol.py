"""Rompetrol Georgia — the price table under the #pricelist anchor of https://www.rompetrol.ge/.

Each fuel has a row with its standard price; the row after it, starting with "-" and saying
"(თვითმომსახურების სადგურებზე)", is the self-service price, which we do not read (docs/domain/fuel-price-sources.md).
"""

from __future__ import annotations

import json

from bs4 import BeautifulSoup

from scraper.core import ParseError, Reading, Station, in_fuel_order, to_coordinate, to_price

URL = "https://www.rompetrol.ge/"
STATIONS_URL = "https://www.rompetrol.ge/routeplanner/stations?language_id=1"

# The station list's service numbers that are fuels (the legend on its stations page, 2026-10-30). efix სუპერი is on
# the price list but not among the services, so every station that sells fuel counts for it (SPEC-0001 REQ-003).
FUEL_BY_SERVICE = {"27": "premium", "29": "regular", "28": "diesel", "30": "diesel"}

FUEL_BY_NAME = {
    "efix სუპერი": "super",
    "efix ევრო პრემიუმი": "premium",
    "efix ევრო რეგულარი": "regular",
    "efix ევრო დიზელი": "diesel",
    "ევრო დიზელი": "diesel",
}


def _text(tag: object) -> str:
    return " ".join(tag.get_text(" ", strip=True).split())  # type: ignore[attr-defined]


def parse(html: str) -> list[Reading]:
    soup = BeautifulSoup(html, "html.parser")
    anchor = soup.find("a", id="pricelist")
    table = anchor.find_next("table") if anchor else None
    if table is None:
        raise ParseError("no price table under #pricelist")
    readings = []
    for tr in table.select("tbody tr"):
        cells = [_text(td) for td in tr.find_all("td")]
        if len(cells) != 2:
            raise ParseError(f"a price row has {len(cells)} cells, not 2")
        name, value = cells
        if name.startswith("-") or "თვითმომსახურების" in name:
            continue
        readings.append(Reading(name, FUEL_BY_NAME.get(name), to_price(value)))
    if not readings:
        raise ParseError("the price table has no rows")
    return readings


def parse_stations(text: str) -> list[Station]:
    """The JSON list behind the stations page's map: id, lat, lng, name, address, services (numbers)."""
    try:
        rows = json.loads(text)
        stations = []
        for row in rows:
            fuels = {FUEL_BY_SERVICE[s] for s in map(str, row.get("services") or []) if s in FUEL_BY_SERVICE}
            if fuels:
                stations.append(Station(str(row["name"]).strip(), str(row.get("address") or "").strip(),
                                        to_coordinate(row["lat"]), to_coordinate(row["lng"]),
                                        in_fuel_order(fuels | {"super"})))
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
        raise ParseError(f"the station list is not the expected shape ({e!r})") from e
    return stations
