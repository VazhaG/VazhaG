"""T3 — reading Rompetrol, Lukoil and Wissol from their saved pages; every company's names map to our fuel list.

SPEC-0001: REQ-002, REQ-006, AC-006. Pages come from tests/fixtures/, never the internet.
"""

from __future__ import annotations

import time
from types import ModuleType

import pytest

from scraper import lukoil, rompetrol, socar, wissol
from scraper.companies import COMPANIES
from scraper.core import FUELS, ParseError, Reading, to_price
from support import ROOT

FIXTURES = ROOT / "tests" / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_rompetrol_reads_the_standard_prices_and_skips_self_service() -> None:
    assert rompetrol.parse(fixture("rompetrol.html")) == [
        Reading("efix სუპერი", "super", 4.68),
        Reading("efix ევრო პრემიუმი", "premium", 4.38),
        Reading("efix ევრო რეგულარი", "regular", 4.08),
        Reading("efix ევრო დიზელი", "diesel", 5.04),
        Reading("ევრო დიზელი", "diesel", 4.97),
    ]


def test_lukoil_reads_the_price_cards_and_skips_a_zero_placeholder() -> None:
    assert lukoil.parse(fixture("lukoil.html")) == [
        Reading("Super Ecto", "super", 4.65),
        Reading("Premium Avangard", "premium", 4.32),
        Reading("Euro Regular", "regular", 4.02),
        Reading("Euro Diesel", "diesel", 5.02),
    ]


def test_wissol_reads_the_standard_prices_in_georgian() -> None:
    readings = wissol.parse(fixture("wissol.html"))
    assert len(readings) == 8
    assert readings[0] == Reading("A1 სუპერი 100", "super", 4.83)
    assert Reading("ეკო სუპერი", "super", 4.68) in readings
    assert Reading("დიზელ ენერჯი", "diesel", 4.93) in readings
    # natural gas: Wissol's own map marks its gas stations so, none as LPG — the owner took that as the
    # confirmation REQ-002 asks for (2026-10-30, docs/domain/fuel-price-sources.md)
    assert Reading("ვისოლ გაზი", "cng", 1.64) in readings


@pytest.mark.parametrize("parse", [rompetrol.parse, lukoil.parse, wissol.parse, socar.parse])
def test_a_page_in_another_shape_is_an_error(parse: object) -> None:
    with pytest.raises(ParseError):
        parse("<html><body><p>გვერდი შეიცვალა</p></body></html>")  # type: ignore[operator]


def test_a_renamed_fuel_is_not_guessed() -> None:
    page = fixture("rompetrol.html").replace("efix ევრო პრემიუმი", "efix ახალი პრემიუმი", 1)
    readings = rompetrol.parse(page)
    assert Reading("efix ახალი პრემიუმი", None, 4.38) in readings


@pytest.mark.parametrize(("module", "name"), [
    (socar, "socar.html"), (rompetrol, "rompetrol.html"), (lukoil, "lukoil.html"), (wissol, "wissol.html"),
])
def test_every_known_name_maps_to_one_fuel_of_our_list(module: ModuleType, name: str) -> None:
    table = module.FUEL_BY_NAME if hasattr(module, "FUEL_BY_NAME") else module.FUEL_BY_CODE
    assert set(table.values()) <= set(FUELS)
    readings = module.parse(fixture(name))
    assert all(r.fuel in FUELS for r in readings if r.fuel is not None)


@pytest.mark.parametrize(("text", "value"), [("4.68", 4.68), (" 4.68 ₾", 4.68), ("4,68", 4.68), ("0.00", 0.0)])
def test_price_text(text: str, value: float) -> None:
    assert to_price(text) == value


@pytest.mark.parametrize("text", ["", "₾", "4.68 ₾/ლ", "ოთხი", "4.6.8"])
def test_price_text_in_another_shape_is_an_error(text: str) -> None:
    with pytest.raises(ParseError):
        to_price(text)


def test_a_price_text_with_a_long_run_of_spaces_is_judged_at_once() -> None:
    # Wissol's price cell reaches to_price with its inner spaces (REQ-007): a pattern that tries every way of sharing
    # a long run of them between two optional parts would hold the whole run for hours on a few megabytes
    start = time.perf_counter()
    with pytest.raises(ParseError):
        to_price("4.95" + " " * 30_000 + "x")
    assert time.perf_counter() - start < 0.5


def test_the_four_companies_and_wissols_switch() -> None:
    assert [c.id for c in COMPANIES] == ["socar", "rompetrol", "lukoil", "wissol"]
    assert len({c.color for c in COMPANIES}) == 4
    assert next(c for c in COMPANIES if c.id == "wissol").enabled is True  # the owner's decision, 2026-10-30
