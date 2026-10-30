"""SOCAR Georgia Petroleum — the price list on https://www.sgp.ge/ge/ (docs/domain/fuel-price-sources.md).

The page is built with Next.js: its data travels in script chunks, each a JSON string,
`self.__next_f.push([1,"…"])`. Joined in order they hold `"GetCurrentPrices":{…,"Results":[…]}` — one row per fuel
with its code, Georgian name and standard price. The rows' `ActionDate` is not a "prices as of" time (2023 dates sit
next to today's prices), so it is not used.
"""

from __future__ import annotations

import json
import re

from scraper.core import ParseError, Reading, Station, in_fuel_order, to_coordinate

URL = "https://www.sgp.ge/ge/"

# The page's own fuel codes -> our common types; the two gases stay separate (SPEC-0001 REQ-002).
FUEL_BY_CODE = {
    "SUPER": "super",
    "PREMIUM": "premium",
    "EURREG": "regular",
    "DIESEL": "diesel",
    "EURODSL": "diesel",
    "LPG": "lpg",
    "CNG": "cng",
}

_CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', re.DOTALL)
_KEY = '"GetCurrentPrices":'


def _page_data(html: str) -> str:
    parts = []
    for m in _CHUNK_RE.finditer(html):
        try:
            parts.append(json.loads(m.group(1)))
        except json.JSONDecodeError:
            continue
    return "".join(parts)


def parse(html: str) -> list[Reading]:
    data = _page_data(html)
    at = data.find(_KEY)
    if at < 0:
        raise ParseError("the page data holds no GetCurrentPrices")
    try:
        block, _ = json.JSONDecoder().raw_decode(data, at + len(_KEY))
        rows = block["Results"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ParseError(f"GetCurrentPrices is not the expected shape ({e!r})") from e
    if not isinstance(rows, list):
        raise ParseError(f"GetCurrentPrices.Results is {type(rows).__name__}, not a list")
    readings = []
    for row in rows:
        try:
            code = str(row["FuelCode"]).strip()
            grade = str(row["FuelNameGeo"]).strip()
            price = float(row["FuelUnitPrice"])
        except (KeyError, TypeError, ValueError) as e:
            raise ParseError(f"a price row is not the expected shape ({e!r})") from e
        readings.append(Reading(grade=grade, fuel=FUEL_BY_CODE.get(code), price=price))
    if not readings:
        raise ParseError("GetCurrentPrices has no rows")
    return readings


STATIONS_URL = "https://sgp.ge/sgp-backend/api/integration/info/get-branches-full-info"


def parse_stations(text: str) -> list[Station]:
    """SOCAR's branch list (the data its /locations page loads): each branch with its place and its own fuel list,
    named as on the price list (FuelNameGe). A branch selling none of our fuels is not a fuel station and is left out."""
    try:
        rows = json.loads(text)["GetBranches"]["Results"]
        stations = []
        for row in rows:
            sold = [f for f in row["Fuels"] if f.get("FuelCode") in FUEL_BY_CODE]
            fuels = in_fuel_order({FUEL_BY_CODE[f["FuelCode"]] for f in sold})
            if fuels:
                stations.append(Station(str(row["AgsNameGe"]).strip(), str(row.get("AgsAddressGe") or "").strip(),
                                        to_coordinate(row["Latitude"]), to_coordinate(row["Longitude"]), fuels,
                                        tuple(str(f["FuelNameGe"]).strip() for f in sold)))
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
        raise ParseError(f"the branch list is not the expected shape ({e!r})") from e
    return stations
