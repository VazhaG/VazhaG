"""Rompetrol Georgia — the price table under the #pricelist anchor of https://www.rompetrol.ge/.

Each fuel has a row with its standard price; the row after it, starting with "-" and saying
"(თვითმომსახურების სადგურებზე)", is the self-service price, which we do not read (docs/domain/fuel-price-sources.md).
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from scraper.core import ParseError, Reading, to_price

URL = "https://www.rompetrol.ge/"

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
