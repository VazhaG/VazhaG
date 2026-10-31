"""PLAN-0003 — Connect („ქონექთი“): its prices from the price block on https://connect.com.ge/.

SPEC-0003: REQ-001, REQ-006; AC-001, AC-004. Pages come from tests/fixtures/, never the internet.
"""

from __future__ import annotations

import urllib.error
from datetime import UTC, datetime

import pytest

from scraper import companies, connect
from scraper.core import ParseError, Reading, company_entry, refresh
from support import ROOT

FIXTURES = ROOT / "tests" / "fixtures"
NOW = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
BEFORE = "2026-10-31T09:00:00Z"
CONNECT = next(c for c in companies.COMPANIES if c.id == "connect")
STANDARD = [
    Reading("სუპერი RON 98", "super", 4.35),
    Reading("პრემიუმი RON 96", "premium", 4.15),
    Reading("რეგულარი RON 93", "regular", 3.95),
    Reading("ევრო დიზელი 10PPM", "diesel", 4.90),
    Reading("დიზელი 10PPM", "diesel", 4.80),
]


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def previous_prices() -> dict[str, dict]:
    return {"connect": {"id": "connect", "name": "Connect", "color": "#ffe900", "source": connect.URL,
                        "time": BEFORE, "basis": "read",
                        "prices": [{"grade": "დიზელი 10PPM", "fuel": "diesel", "price": 4.80}]}}


def test_connect_reads_the_standard_price_of_each_card_and_never_self_service() -> None:
    assert connect.parse(fixture("connect.html")) == STANDARD


def test_the_two_prices_swapping_places_in_a_card_changes_nothing() -> None:
    # REQ-001: read by its label, never by its place — the first card already lists self-service first
    standard = '<span class="fpc-plabel">სტანდარტული</span>\n                    <span class="fpc-pstd">4.15₾</span>'
    own = '<span class="fpc-plabel">თვითმომსახურება</span>\n                    <span class="fpc-pself">3.95₾</span>'
    page = fixture("connect.html")
    assert standard in page and own in page
    swapped = page.replace(standard, "\0").replace(own, standard).replace("\0", own)
    assert connect.parse(swapped) == STANDARD


def test_the_entry_names_connect_its_colour_source_and_reading_time() -> None:
    entry = company_entry(CONNECT, connect.parse(fixture("connect.html")), NOW)
    assert {k: entry[k] for k in ("id", "name", "color", "source", "time", "basis")} == {
        "id": "connect", "name": "Connect", "color": "#ffe900", "source": "https://connect.com.ge/",
        "time": "2026-10-31T12:00:00Z", "basis": "read"}
    assert [p["fuel"] for p in entry["prices"]] == ["super", "premium", "regular", "diesel", "diesel"]


def test_a_name_not_in_the_table_is_left_out_and_the_others_are_read() -> None:
    page = fixture("connect.html").replace("სუპერი RON 98", "სუპერი RON 100", 1)
    entries, log, read = refresh([CONNECT], previous_prices(), lambda url: page, NOW)
    assert read == 1
    assert [p["grade"] for p in entries[0]["prices"]] == [r.grade for r in STANDARD[1:]]
    assert log == ["Connect: „სუპერი RON 100“ is not in the fuel table — left out"]


@pytest.mark.parametrize("page", [
    "<html><body><p>გვერდი შეიცვალა</p></body></html>",  # no price block
    fixture("connect.html").replace("4.15₾", "ფასი", 1),  # a price that is not a number
    fixture("connect.html").replace('<span class="fpc-pstd">4.15₾</span>', "", 1),  # a card without its price
])
def test_a_page_in_another_shape_keeps_the_previous_prices(page: str) -> None:
    previous = previous_prices()
    entries, log, read = refresh([CONNECT], previous, lambda url: page, NOW)
    assert (entries, read) == ([previous["connect"]], 0)
    assert len(log) == 1 and log[0].startswith("Connect: not read — ")


@pytest.mark.parametrize("answer", [
    urllib.error.HTTPError(connect.URL, 403, "Forbidden", {}, None),  # type: ignore[arg-type]
    urllib.error.HTTPError(connect.URL, 429, "Too Many Requests", {}, None),  # type: ignore[arg-type]
    "<html><head><title>Just a moment...</title></head><body>Enable JavaScript and cookies to continue</body></html>",
])
def test_a_refusal_or_a_browser_check_keeps_the_previous_prices_and_is_not_tried_again(answer: object) -> None:
    # REQ-006: no second try and no other name — the previous prices stay and the log says why, in one line
    asked: list[str] = []

    def get(url: str) -> str:
        asked.append(url)
        if isinstance(answer, BaseException):
            raise answer
        return str(answer)

    previous = previous_prices()
    entries, log, read = refresh([CONNECT], previous, get, NOW)
    assert asked == [connect.URL]
    assert (entries, read) == ([previous["connect"]], 0)
    assert len(log) == 1 and log[0].startswith("Connect: not read — ")


def test_connect_is_read_with_a_switch_like_wissols() -> None:
    assert CONNECT.name == "Connect" and CONNECT.url == "https://connect.com.ge/" and CONNECT.enabled is True
    assert companies.CONNECT_ENABLED is True  # the owner's decision, 2026-10-31 (SPEC-0003 REQ-004)
    with pytest.raises(ParseError):
        connect.parse("")
