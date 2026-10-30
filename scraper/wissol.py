"""Wissol — the price rows (button.prices_row) on https://wissol.ge/ka/fuel-prices: the name, the standard price and,
for most fuels, a self-service price (class is-self-service), which we do not read.

Wissol's terms forbid using the site's information; the owner decided to include it anyway (SPEC-0001 §3, §7) — it is
switched off with one setting in scraper/companies.py.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from scraper.core import ParseError, Reading, to_price

URL = "https://wissol.ge/ka/fuel-prices"

FUEL_BY_NAME = {
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
