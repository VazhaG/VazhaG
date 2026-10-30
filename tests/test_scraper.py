"""The price reader — SPEC-0001 REQ-006, AC-006 (SOCAR's part). Pages come from tests/fixtures/, never the internet."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

import scraper.__main__ as cli
from scraper import socar
from scraper.companies import COMPANIES
from scraper.core import ParseError, Reading, company_entry
from support import ROOT

FIXTURES = ROOT / "tests" / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_socar_reads_every_row_of_the_saved_page() -> None:
    readings = socar.parse(fixture("socar.html"))
    by_grade = {r.grade: r for r in readings}
    assert len(readings) == 7
    assert by_grade["ნანო სუპერი"] == Reading("ნანო სუპერი", "super", 4.65)
    assert by_grade["ნანო პრემიუმი"].fuel == "premium"
    assert by_grade["ნანო ევრო რეგულარი"].fuel == "regular"
    assert by_grade["ევრო 5 დიზელი"].fuel == "diesel"
    assert by_grade["ნანო ევრო 5 დიზელი"].fuel == "diesel"


def test_socar_gas_waits_for_the_owner() -> None:
    readings = socar.parse(fixture("socar.html"))
    assert {r.grade for r in readings if r.fuel is None} == {"თხევადი აირი", "ბუნებრივი აირი"}


@pytest.mark.parametrize("html", [
    "<html><body>nothing here</body></html>",
    '<script>self.__next_f.push([1,"\\"GetCurrentPrices\\":{\\"Status\\":\\"1\\"}"])</script>',
    '<script>self.__next_f.push([1,"\\"GetCurrentPrices\\":{\\"Results\\":[]}"])</script>',
    '<script>self.__next_f.push([1,"\\"GetCurrentPrices\\":{\\"Results\\":[{\\"FuelCode\\":\\"SUPER\\"}]}"])</script>',
])
def test_socar_page_in_another_shape_is_an_error(html: str) -> None:
    with pytest.raises(ParseError):
        socar.parse(html)


def test_company_entry_keeps_source_time_and_known_fuels_only() -> None:
    company = COMPANIES[0]
    readings = [Reading("A", "super", 4.5), Reading("B", None, 2.0)]
    entry = company_entry(company, readings, datetime(2026, 10, 30, 12, 0, tzinfo=UTC))
    assert entry["source"] == company.url
    assert entry["time"] == "2026-10-30T12:00:00Z"
    assert entry["basis"] == "read"
    assert entry["prices"] == [{"grade": "A", "fuel": "super", "price": 4.5}]


def test_cli_writes_the_data_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "fetch", lambda url: fixture("socar.html"))
    out = tmp_path / "prices.json"
    assert cli.main(["--only", "socar", "--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    (entry,) = data["companies"]
    assert entry["id"] == "socar"
    assert len(entry["prices"]) == 5


def test_cli_with_nothing_read_leaves_the_file_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(url: str) -> str:
        raise OSError("network down")

    monkeypatch.setattr(cli, "fetch", broken)
    out = tmp_path / "prices.json"
    out.write_text("{}", encoding="utf-8")
    assert cli.main(["--out", str(out)]) == 1
    assert out.read_text(encoding="utf-8") == "{}"
