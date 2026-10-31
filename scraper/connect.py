"""Connect („ქონექთი“) — the price block (div#fpc…) on https://connect.com.ge/: one card per fuel, with its name and
two prices labelled „სტანდარტული“ (class fpc-feat-std / fpc-pstd) and „თვითმომსახურება“ (fpc-feat-self / fpc-pself).
The standard price is read by its class, never by its place: the two swap places between cards (on 2026-10-31 the
first card lists self-service first). The self-service price is not read, as for the other companies.

Connect's terms forbid spreading the site's content without written consent; the owner decided to include it anyway
(SPEC-0003 REQ-004) — it is switched off with one setting in scraper/companies.py.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from scraper.core import ParseError, Reading, to_price

URL = "https://connect.com.ge/"

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
