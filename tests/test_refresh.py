"""T3 — one reading round: a failed or misread company keeps its previous prices with their time, the others are
updated; a switched-off company is removed.

SPEC-0001: REQ-006, REQ-007, AC-005.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from scraper.core import Company, ParseError, Reading, overdue, problems, refresh

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
BEFORE = "2026-10-30T09:00:00Z"


def company(cid: str, readings: list[Reading] | None, enabled: bool = True) -> Company:
    def parse(html: str) -> list[Reading]:
        if readings is None:
            raise ParseError("page changed")
        return readings

    return Company(id=cid, name=cid.upper(), color="#123456", url=f"https://{cid}.example/", parse=parse,
                   enabled=enabled)


def old_entry(cid: str, value: float) -> dict:
    return {"id": cid, "name": cid.upper(), "color": "#123456", "source": f"https://{cid}.example/", "time": BEFORE,
            "basis": "read", "prices": [{"grade": "დიზელი", "fuel": "diesel", "price": value}]}


def fetch_all(url: str) -> str:
    if url.startswith("https://down."):
        raise OSError("connection refused")
    return "<html></html>"


def test_one_failure_does_not_stop_the_others() -> None:
    companies = [
        company("down", [Reading("დიზელი", "diesel", 4.9)]),
        company("zero", [Reading("დიზელი", "diesel", 0.0)]),
        company("tenth", [Reading("დიზელი", "diesel", 0.49)]),
        company("good", [Reading("დიზელი", "diesel", 4.95)]),
    ]
    previous = {c: old_entry(c, 4.9) for c in ("down", "zero", "tenth", "good")}
    entries, log, read = refresh(companies, previous, fetch_all, NOW)
    by_id = {e["id"]: e for e in entries}
    assert read == 1
    assert by_id["good"]["time"] == "2026-10-30T12:00:00Z"
    assert by_id["good"]["prices"] == [{"grade": "დიზელი", "fuel": "diesel", "price": 4.95}]
    for cid in ("down", "zero", "tenth"):
        assert by_id[cid] == previous[cid]  # the old price, with its old time
    assert sum("not read" in line for line in log) == 3
    assert any(line.startswith("DOWN:") and "connection refused" in line for line in log)


def test_a_failed_company_with_no_previous_prices_is_simply_absent() -> None:
    entries, log, read = refresh([company("new", None)], {}, fetch_all, NOW)
    assert (entries, read) == ([], 0)
    assert log == ["NEW: not read — page changed"]


def diesel(value: float) -> list[Reading]:
    return [Reading("დიზელი", "diesel", value)]


@pytest.mark.parametrize(("value", "ok"), [(0.49, False), (0.50, True), (15.00, True), (15.01, False)])
def test_price_limits(value: float, ok: bool) -> None:
    # AC-005: 0.50–15.00 GEL
    assert (problems(diesel(value), None, NOW) == []) is ok


@pytest.mark.parametrize(("value", "ok"), [(5.00, True), (3.00, True), (5.01, False), (2.99, False)])
def test_jump_limit_from_the_previous_price(value: float, ok: bool) -> None:
    # AC-005: at most 25 % from the same grade's previous price, 4.00 GEL
    assert (problems(diesel(value), old_entry("a", 4.00), NOW) == []) is ok


def test_a_tenth_of_the_price_inside_the_limits_is_caught_by_the_jump_rule() -> None:
    assert problems(diesel(0.504), None, NOW) == []
    assert problems(diesel(0.504), old_entry("a", 5.04), NOW) != []


def test_the_jump_rule_ignores_a_previous_price_older_than_seven_days() -> None:
    week_old = old_entry("a", 4.00) | {"time": (NOW - timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    assert problems(diesel(6.00), week_old, NOW) == []
    assert problems(diesel(6.00), old_entry("a", 4.00), NOW) != []


def test_a_new_grade_has_nothing_to_jump_from() -> None:
    assert problems([Reading("ახალი", "diesel", 9.0)], old_entry("a", 4.00), NOW) == []


@pytest.mark.parametrize(("hours", "late"), [(47, False), (48, True)])
def test_a_company_not_read_for_48_hours_is_overdue(hours: float, late: bool) -> None:
    entry = old_entry("a", 4.0) | {"time": (NOW - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    assert (overdue([company("a", [])], [entry], NOW) == ["A"]) is late


def test_an_enabled_company_with_no_prices_at_all_is_overdue_a_switched_off_one_is_not() -> None:
    assert overdue([company("a", []), company("off", [], enabled=False)], [], NOW) == ["A"]


def test_unknown_fuel_names_are_logged_and_left_out() -> None:
    readings = [Reading("დიზელი", "diesel", 4.9), Reading("უცნობი", None, 3.0)]
    entries, log, _read = refresh([company("a", readings)], {}, fetch_all, NOW)
    assert entries[0]["prices"] == [{"grade": "დიზელი", "fuel": "diesel", "price": 4.9}]
    assert log == ["A: „უცნობი“ is not in the fuel table — left out"]


def test_a_page_with_no_known_fuel_is_a_failed_reading() -> None:
    previous = {"a": old_entry("a", 4.9)}
    entries, _log, read = refresh([company("a", [Reading("უცნობი", None, 3.0)])], previous, fetch_all, NOW)
    assert (entries, read) == ([previous["a"]], 0)


def test_a_switched_off_company_is_not_read_and_its_prices_are_removed() -> None:
    def never(url: str) -> str:
        raise AssertionError("a switched-off company must not be fetched")

    entries, log, read = refresh([company("off", [], enabled=False)], {"off": old_entry("off", 4.9)}, never, NOW)
    assert (entries, read) == ([], 0)
    assert log == ["OFF: switched off — not read, its prices removed"]


def test_only_some_companies_keeps_the_others_as_they_were() -> None:
    previous = {"a": old_entry("a", 4.9), "b": old_entry("b", 4.8)}
    companies = [company("a", [Reading("დიზელი", "diesel", 4.95)]), company("b", [Reading("დიზელი", "diesel", 4.7)])]
    entries, _log, read = refresh(companies, previous, fetch_all, NOW, only={"a"})
    by_id = {e["id"]: e for e in entries}
    assert read == 1
    assert by_id["a"]["prices"][0]["price"] == 4.95
    assert by_id["b"] == previous["b"]
