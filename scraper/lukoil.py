"""Lukoil Georgia — the price cards on https://www.lukoil.ge/: an image with alt "Price", then the price and the name.

A card priced 0.00 (on 2026-10-30: "Super Ecto 100") is a fuel not on sale now, not a price — it is skipped.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from scraper.core import ParseError, Reading, to_price

URL = "https://www.lukoil.ge/"

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
