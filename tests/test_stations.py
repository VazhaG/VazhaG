"""T4 — the companies' station lists: where each station is and which fuels it sells.

SPEC-0001: REQ-001, REQ-003 (which stations count for a fuel), AC-002 (a station with an unknown place is not shown).
Fixtures (tests/fixtures/*-stations.*), read on 2026-10-30: SOCAR's branch list — four records as they came;
Rompetrol's station list — two records without their `infowindow` HTML; Lukoil's map script — its first three
markers; Wissol's map page — five records of its location list only.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from scraper import lukoil, rompetrol, socar, wissol
from scraper.core import MAX_STATIONS, PETROL, Company, ParseError, Reading, Station, refresh_stations
from support import ROOT

FIXTURES = ROOT / "tests" / "fixtures"
NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_socar_stations_carry_their_own_fuels() -> None:
    stations = socar.parse_stations(fixture("socar-stations.json"))
    assert len(stations) == 3  # the record with no fuel is not a fuel station
    first = stations[0]
    assert first == Station("აეროპორტი 1", first.address, 41.68782, 44.89672, ("regular", "premium", "diesel"),
                            ("ნანო პრემიუმი", "ევრო 5 დიზელი", "ნანო ევრო 5 დიზელი", "ნანო ევრო რეგულარი"))
    assert first.address.startswith("ქ. თბილისი")
    prices = {r.grade for r in socar.parse(fixture("socar.html"))}
    assert {g for s in stations for g in s.grades} <= prices  # the station list names fuels as the price list does
    assert any({"lpg", "cng"} <= set(s.fuels) for s in stations)


def test_rompetrol_station_fuels_come_from_its_services_and_super_is_assumed() -> None:
    with_premium, without_premium = rompetrol.parse_stations(fixture("rompetrol-stations.json"))
    assert "premium" in with_premium.fuels
    assert "premium" not in without_premium.fuels
    for s in (with_premium, without_premium):
        assert {"regular", "diesel", "super"} <= set(s.fuels)  # super: not in the services, so assumed (REQ-003)
        assert not {"lpg", "cng"} & set(s.fuels)
    assert with_premium.name == "ზმკ"
    assert (with_premium.lat, with_premium.lng) == (41.672493, 44.876102)
    assert "efix ევრო პრემიუმი" in with_premium.grades
    prices = {r.grade for r in rompetrol.parse(fixture("rompetrol.html"))}
    assert set(with_premium.grades) | set(without_premium.grades) <= prices  # named as on the price list


def test_lukoil_stations_come_from_the_map_markers_with_petrol_assumed() -> None:
    stations = lukoil.parse_stations(fixture("lukoil-stations.html"))
    assert len(stations) == 3
    assert stations[0].lat == 41.6824391215882
    assert stations[0].address.startswith("თბილისი,")
    assert all(s.fuels == PETROL for s in stations)


def test_wissol_keeps_fuel_stations_and_natural_gas_stations_only() -> None:
    stations = wissol.parse_stations(fixture("wissol-stations.html"))
    assert [s.fuels for s in stations] == [PETROL, PETROL, ("cng",)]  # the service centre and the shop are left out
    assert 41.0 < stations[0].lat < 43.7 and 39.9 < stations[0].lng < 46.8  # [lng, lat] read the right way round


@pytest.mark.parametrize("parse", [socar.parse_stations, rompetrol.parse_stations, lukoil.parse_stations,
                                   wissol.parse_stations])
def test_a_station_source_in_another_shape_is_an_error(parse: object) -> None:
    with pytest.raises(ParseError):
        parse("<html><body>გვერდი შეიცვალა</body></html>")  # type: ignore[operator]


def company(cid: str, stations: list[Station] | None) -> Company:
    def parse_stations(text: str) -> list[Station]:
        if stations is None:
            raise ParseError("page changed")
        return stations

    return Company(id=cid, name=cid.upper(), color="#123456", url=f"https://{cid}.example/prices",
                   parse=lambda html: [Reading("x", "diesel", 4.0)], stations_url=f"https://{cid}.example/map",
                   parse_stations=parse_stations)


def at(lat: float | None, lng: float | None, fuels: tuple[str, ...] = PETROL) -> Station:
    return Station("", "მისამართი", lat, lng, fuels)


def old_entry(cid: str, count: int) -> dict:
    return {"id": cid, "name": cid.upper(), "color": "#123456", "source": f"https://{cid}.example/map",
            "time": "2026-10-30T09:00:00Z", "basis": "read",
            "stations": [{"name": "", "address": "a", "lat": 41.7, "lng": 44.8, "fuels": list(PETROL)}] * count}


def get(url: str) -> str:
    return ""


def test_a_station_with_an_unknown_or_foreign_place_is_left_out() -> None:
    stations = [at(41.7, 44.8), at(None, 44.8), at(0.0, 0.0), at(55.75, 37.62), at(41.6, 41.6)]
    entries, log, read = refresh_stations([company("a", stations)], {}, get, NOW)
    assert read == 1
    assert [(s["lat"], s["lng"]) for s in entries[0]["stations"]] == [(41.7, 44.8), (41.6, 41.6)]
    assert log == ["A: 3 station(s) without a place in Georgia — left out"]


def test_a_station_list_that_shrank_by_half_is_a_misreading() -> None:
    previous = {"a": old_entry("a", 10)}
    entries, log, read = refresh_stations([company("a", [at(41.7, 44.8)] * 4)], previous, get, NOW)
    assert (entries, read) == ([previous["a"]], 0)
    assert "not read" in log[0]
    entries, _log, read = refresh_stations([company("a", [at(41.7, 44.8)] * 5)], previous, get, NOW)
    assert read == 1 and len(entries[0]["stations"]) == 5


def test_a_station_list_twice_as_long_as_the_last_one_is_a_misreading() -> None:
    # Every visitor's phone downloads and draws the whole list (AC-001's 10 seconds): one that suddenly doubled is not
    # believed, like one that halved
    previous = {"a": old_entry("a", 10)}
    entries, log, read = refresh_stations([company("a", [at(41.7, 44.8)] * 21)], previous, get, NOW)
    assert (entries, read) == ([previous["a"]], 0)
    assert log == [("A: stations not read — 21 station(s), the last list had 10 (the previous stations stay, with "
                    "their time)")]
    entries, _log, read = refresh_stations([company("a", [at(41.7, 44.8)] * 20)], previous, get, NOW)
    assert read == 1 and len(entries[0]["stations"]) == 20


def test_no_company_list_is_longer_than_max_stations() -> None:
    # The first list has no previous one to compare with; the longest list now is Wissol's, 147 (2026-10-30)
    entries, log, read = refresh_stations([company("a", [at(41.7, 44.8)] * (MAX_STATIONS + 1))], {}, get, NOW)
    assert (entries, read) == ([], 0)
    assert log == [f"A: stations not read — {MAX_STATIONS + 1} station(s), more than {MAX_STATIONS}"]
    entries, _log, read = refresh_stations([company("a", [at(41.7, 44.8)] * MAX_STATIONS)], {}, get, NOW)
    assert read == 1


def test_a_list_older_than_7_days_no_longer_judges_the_new_one() -> None:
    # Otherwise one wrong list that got through would refuse every true list after it, for good
    stale = {"a": old_entry("a", 100) | {"time": "2026-10-22T12:00:00Z"}}  # 8 days before NOW
    entries, _log, read = refresh_stations([company("a", [at(41.7, 44.8)] * 10)], stale, get, NOW)
    assert read == 1 and len(entries[0]["stations"]) == 10
    recent = {"a": old_entry("a", 100) | {"time": "2026-10-24T12:00:00Z"}}  # 6 days before NOW
    entries, _log, read = refresh_stations([company("a", [at(41.7, 44.8)] * 10)], recent, get, NOW)
    assert (entries, read) == ([recent["a"]], 0)


def test_a_broken_character_keeps_the_previous_list() -> None:
    # Half of a UTF-16 pair cannot be written as UTF-8 (see test_refresh.py): that list is a misreading
    previous = {"a": old_entry("a", 1)}
    broken = Station("", "მისამართი \udc00", 41.7, 44.8, PETROL)
    entries, log, read = refresh_stations([company("a", [broken])], previous, get, NOW)
    assert (entries, read) == ([previous["a"]], 0)
    assert log[0].startswith("A: stations not read — ") and "\udc00" not in log[0]


def test_a_failed_station_list_keeps_the_previous_one() -> None:
    previous = {"a": old_entry("a", 3)}
    entries, log, read = refresh_stations([company("a", None)], previous, get, NOW)
    assert (entries, read) == ([previous["a"]], 0)
    assert log == ["A: stations not read — page changed (the previous stations stay, with their time)"]


def test_grades_are_written_only_when_the_list_names_them() -> None:
    named = Station("", "a", 41.7, 44.8, ("diesel",), ("ევრო დიზელი",))
    entries, _log, _read = refresh_stations([company("a", [named, at(41.7, 44.8)])], {}, get, NOW)
    first, second = entries[0]["stations"]
    assert first["grades"] == ["ევრო დიზელი"]
    assert "grades" not in second


def test_station_entry_shape() -> None:
    entries, _log, _read = refresh_stations([company("a", [at(41.7, 44.8, ("regular", "cng"))])], {}, get, NOW)
    assert entries == [{"id": "a", "name": "A", "color": "#123456", "source": "https://a.example/map",
                        "time": "2026-10-30T12:00:00Z", "basis": "read",
                        "stations": [{"name": "", "address": "მისამართი", "lat": 41.7, "lng": 44.8,
                                      "fuels": ["regular", "cng"]}]}]
