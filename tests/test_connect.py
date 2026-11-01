"""PLAN-0003 — Connect („ქონექთი“): its prices from the price block on https://connect.com.ge/ (T1), and its stations
from the list its map page loads, asked for with the code the map page hands out (T2).

SPEC-0003: REQ-001, REQ-002, REQ-006; AC-001, AC-002, AC-003, AC-004. Pages come from tests/fixtures/, never the
internet: connect.html — the price block; connect-map.html — the map page's one line with the list's code (made up);
connect-stations.json — five records of the list as they came on 2026-10-31 (reformatted), Kareli's with its broken
longitude among them.
"""

from __future__ import annotations

import dataclasses
import http.server
import importlib.util
import json
import threading
import time
import urllib.error
import urllib.parse
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

import scraper.__main__ as cli
from scraper import companies, connect, lukoil, rompetrol, socar, wissol
from scraper.core import (
    PETROL,
    USER_AGENT,
    Company,
    ParseError,
    Reading,
    company_entry,
    fetch,
    refresh,
    refresh_stations,
)
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


CARD = '<div class="fpc-card"><div class="fpc-card-name">დიზელი 10PPM</div><span class="fpc-pstd">4.80₾</span></div>'


def test_a_page_of_cards_nested_thousands_deep_is_refused_at_once() -> None:
    # security review S1: each card's own search walks everything inside it, so cards nested in cards cost the
    # square of their number — 2 000 took 18 s, and the run has no deadline for reading a page it has downloaded
    depth = 3_000
    page = ('<div id="fpc1">' + '<div class="fpc-card">' * depth
            + '<div class="fpc-card-name">დიზელი 10PPM</div><span class="fpc-pstd">4.80₾</span>'
            + "</div>" * depth + "</div>")
    start = time.perf_counter()
    with pytest.raises(ParseError):
        connect.parse(page)
    assert time.perf_counter() - start < 1


def test_more_cards_than_the_block_holds_are_refused() -> None:
    with pytest.raises(ParseError, match="21 price cards"):
        connect.parse(f'<div id="fpc1">{CARD * 21}</div>')
    assert len(connect.parse(f'<div id="fpc1">{CARD * 20}</div>')) == 20


def test_a_block_cut_by_the_reading_window_is_refused_not_read_in_part() -> None:
    # correctness review C4: a block grown past the window would lose its last cards without a word
    padding = "<!-- " + "ბ" * connect.BLOCK_CHARS + " -->"
    page = fixture("connect.html").replace(
        '                <div class="fpc-card">\n            <div class="fpc-card-name">დიზელი 10PPM</div>',
        padding + '\n                <div class="fpc-card">\n            <div class="fpc-card-name">დიზელი 10PPM</div>', 1)
    assert padding in page
    with pytest.raises(ParseError, match="does not end"):
        connect.parse(page)


def test_a_block_that_is_not_a_div_is_refused() -> None:
    # its end is found by counting <div> and </div>: another wrapper would make that count meaningless
    page = fixture("connect.html").replace('<div id="fpc22875a6">', '<section id="fpc22875a6">', 1)
    with pytest.raises(ParseError, match="no price block"):
        connect.parse(page)


def test_only_the_first_price_block_is_read() -> None:
    page = fixture("connect.html").replace("</body>", "<p>სხვა</p>" + fixture("connect.html") + "</body>", 1)
    assert connect.parse(page) == STANDARD


def test_the_block_is_found_far_down_a_large_page_and_read_alone() -> None:
    page = "<html><body>" + "<p>ტექსტი</p>" * 300_000 + fixture("connect.html")  # about 8 MB before the block
    start = time.perf_counter()
    assert connect.parse(page) == STANDARD
    assert time.perf_counter() - start < 1


def test_connect_is_read_with_a_switch_like_wissols() -> None:
    assert CONNECT.name == "Connect" and CONNECT.url == "https://connect.com.ge/" and CONNECT.enabled is True
    assert companies.CONNECT_ENABLED is True  # the owner's decision, 2026-10-31 (SPEC-0003 REQ-004)
    with pytest.raises(ParseError):
        connect.parse("")


# T2 — the stations (REQ-002, REQ-006; AC-002, AC-003, AC-004 ბ, გ, დ)
CODE = "0f1e2d3c4b"  # the made-up code in connect-map.html
CHALLENGE = "<html><head><title>Just a moment...</title></head><body>Enable JavaScript and cookies</body></html>"


def connect_site(map_page: str | None = None, list_answer: object = None) -> tuple[list[str], Callable[[str], str]]:
    """A stand-in for connect.com.ge: (the addresses asked, the fetcher). An answer that is an exception is raised."""
    asked: list[str] = []

    def get(url: str) -> str:
        asked.append(url)
        if url == connect.URL:
            return fixture("connect.html")
        if url == connect.MAP_URL:
            return fixture("connect-map.html") if map_page is None else map_page
        if url.startswith(connect.LIST_URL + "?"):
            if isinstance(list_answer, BaseException):
                raise list_answer
            return fixture("connect-stations.json") if list_answer is None else str(list_answer)
        raise AssertionError(f"an address outside REQ-006: {url}")

    return asked, get


def previous_stations(count: int = 4) -> dict[str, dict]:
    station = {"name": "აბაშა", "address": "ნორიო", "lat": 42.2, "lng": 42.2, "fuels": list(PETROL)}
    return {"connect": {"id": "connect", "name": "Connect", "color": "#ffe900", "source": connect.MAP_URL,
                        "time": BEFORE, "basis": "read", "stations": [station] * count}}


def test_the_map_page_gives_the_code_and_the_list_is_asked_at_its_fixed_address_with_it() -> None:
    asked, get = connect_site()
    text = connect.stations_text(get)
    assert len(asked) == 2 and asked[0] == "https://connect.com.ge/map/" == connect.MAP_URL
    address, query = asked[1].split("?", 1)
    assert address == "https://connect.com.ge/wp-admin/admin-ajax.php" == connect.LIST_URL
    assert urllib.parse.parse_qs(query, keep_blank_values=True) == {
        "action": ["asl_load_stores"], "nonce": [CODE], "asl_lang": [""], "load_all": ["1"], "layout": ["0"]}
    assert json.loads(text)[0]["id"] == "1276"


def test_connects_stations_have_their_town_address_place_and_petrol_and_diesel() -> None:
    asked, get = connect_site()
    entries, log, read = refresh_stations([CONNECT], {}, get, NOW)
    assert read == 1 and len(asked) == 2
    entry = entries[0]
    assert (entry["id"], entry["source"], entry["time"]) == ("connect", "https://connect.com.ge/map/",
                                                            "2026-10-31T12:00:00Z")
    assert [(s["name"], s["address"]) for s in entry["stations"]] == [
        ("აბაშა", "ნორიო, სოფელი საბოკუჩავო"), ("აბაშა", "კ.გამსახურდიას ქუჩა #39"),
        ("თბილისი", "გურამიშვილის გამზ. #170"), ("თბილისი", "ქავთარაძე #1")]
    assert (entry["stations"][2]["lat"], entry["stations"][2]["lng"]) == (41.7824887, 44.79799482)
    assert all(s["fuels"] == list(PETROL) for s in entry["stations"])
    assert log == ["Connect: 1 station(s) without a place in Georgia — left out"]  # Kareli: longitude 443.896938


def test_an_empty_street_gives_the_station_its_city_line_as_the_address() -> None:
    text = fixture("connect-stations.json").replace('"street": "ქავთარაძე #1"', '"street": ""', 1)
    assert connect.parse_stations(text)[-1].address == "1 Petre Kavtaradze St, Tbilisi"


@pytest.mark.parametrize("map_page", [
    "<html><body>no store locator here</body></html>",
    fixture("connect-map.html").replace(CODE, "abc&action=x"),
    fixture("connect-map.html").replace(CODE, "0f1e2\n3c4b"),
    fixture("connect-map.html").replace(CODE, "a" * 10_000),
    CHALLENGE,
])
def test_no_code_or_a_code_in_another_shape_asks_nothing_more_and_keeps_the_previous_stations(map_page: str) -> None:
    # REQ-006: only a code in a code's shape passes from the page into a request
    asked, get = connect_site(map_page=map_page)
    previous = previous_stations()
    entries, log, read = refresh_stations([CONNECT], previous, get, NOW)
    assert asked == [connect.MAP_URL]
    assert (entries, read) == ([previous["connect"]], 0)
    assert len(log) == 1 and log[0].startswith("Connect: stations not read — ")


@pytest.mark.parametrize("answer", [
    "-1", "0", "{}", "[]", "not json", '["a text, not a station"]', CHALLENGE,
    json.dumps(json.loads(fixture("connect-stations.json"))[:1]),  # one station where four were: less than half
    urllib.error.HTTPError(connect.LIST_URL, 403, "Forbidden", {}, None),  # type: ignore[arg-type]
    urllib.error.HTTPError(connect.LIST_URL, 429, "Too Many Requests", {}, None),  # type: ignore[arg-type]
])
def test_a_list_answer_that_is_not_a_list_of_stations_keeps_the_previous_stations(answer: object) -> None:
    asked, get = connect_site(list_answer=answer)
    previous = previous_stations()
    entries, log, read = refresh_stations([CONNECT], previous, get, NOW)
    assert len(asked) == 2  # no second try
    assert (entries, read) == ([previous["connect"]], 0)
    assert len(log) == 1 and log[0].startswith("Connect: stations not read — ")


@pytest.mark.parametrize(("code", "taken"), [("a" * 5, False), ("a" * 6, True), ("Z9" * 16, True), ("a" * 33, False)])
def test_a_code_is_six_to_thirty_two_letters_and_digits(code: str, taken: bool) -> None:
    asked, get = connect_site(map_page=fixture("connect-map.html").replace(CODE, code))
    if taken:
        connect.stations_text(get)
        assert urllib.parse.parse_qs(asked[1].split("?", 1)[1])["nonce"] == [code]
    else:
        with pytest.raises(ParseError):
            connect.stations_text(get)
        assert asked == [connect.MAP_URL]


@pytest.mark.parametrize(("answer", "why"), [
    ("not json", "the station list is not JSON"),
    ("-1", "the station list is not a list"),
    ("{}", "the station list is not a list"),
    ('["a text, not a station"]', "a station is not the expected shape"),
    ("[]", "no station with a place in Georgia"),
])
def test_the_log_says_why_the_list_was_not_read(answer: str, why: str) -> None:
    _asked, get = connect_site(list_answer=answer)
    _entries, log, _read = refresh_stations([CONNECT], previous_stations(), get, NOW)
    assert log[0].startswith(f"Connect: stations not read — {why}")


def test_a_refused_map_page_is_not_tried_again() -> None:
    def get(url: str) -> str:
        asked.append(url)
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)  # type: ignore[arg-type]

    asked: list[str] = []
    previous = previous_stations()
    entries, _log, read = refresh_stations([CONNECT], previous, get, NOW)
    assert asked == [connect.MAP_URL]
    assert (entries, read) == ([previous["connect"]], 0)


def test_the_other_four_companies_still_ask_for_their_station_list_once() -> None:
    pages = {socar.STATIONS_URL: "socar-stations.json", rompetrol.STATIONS_URL: "rompetrol-stations.json",
             lukoil.STATIONS_URL: "lukoil-stations.html", wissol.STATIONS_URL: "wissol-stations.html"}
    asked, connect_get = connect_site()
    others: list[str] = []

    def get(url: str) -> str:
        if url in pages:
            others.append(url)
            return fixture(pages[url])
        return connect_get(url)

    _entries, _log, read = refresh_stations(companies.COMPANIES, {}, get, NOW)
    assert read == 5
    assert others == list(pages) and len(asked) == 2


@pytest.fixture
def connect_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[str, list[tuple[str, str]]]]:
    """connect.com.ge on a local port: (its address, every request's path and User-Agent). Its map page points the
    station list elsewhere — the reader must still ask at its own fixed address."""
    seen: list[tuple[str, str]] = []
    pages = {"/": fixture("connect.html"),
             "/map/": fixture("connect-map.html").replace("https://connect.com.ge/wp-admin/admin-ajax.php",
                                                          "https://elsewhere.example/steal"),
             "/wp-admin/admin-ajax.php": fixture("connect-stations.json")}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            seen.append((self.path, self.headers.get("User-Agent", "")))
            body = pages.get(self.path.split("?", 1)[0], "").encode("utf-8")
            self.send_response(200 if body else 404)
            self.send_header("Content-Type", "text/html; charset=UTF-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:  # keep the test output clean
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    monkeypatch.setattr(connect, "MAP_URL", base + "/map/")
    monkeypatch.setattr(connect, "LIST_URL", base + "/wp-admin/admin-ajax.php")
    yield base, seen
    server.shutdown()
    server.server_close()


def test_one_round_asks_connect_exactly_three_times_by_our_programs_name(
        connect_server: tuple[str, list[tuple[str, str]]]) -> None:
    # AC-003: the price page, the map page, the list — at their fixed addresses, the third with the page's code
    base, seen = connect_server
    company = dataclasses.replace(CONNECT, url=base + "/", stations_url=base + "/map/")
    _p, _log, read = refresh([company], {}, fetch, NOW)
    _s, _log, read_stations = refresh_stations([company], {}, fetch, NOW)
    assert (read, read_stations) == (1, 1)
    assert [path.split("?", 1)[0] for path, _ in seen] == ["/", "/map/", "/wp-admin/admin-ajax.php"]
    assert {agent for _, agent in seen} == {USER_AGENT}
    assert urllib.parse.parse_qs(seen[2][0].split("?", 1)[1])["nonce"] == [CODE]


# T3 — the switch (REQ-004; AC-009)
def companies_with_connect_switched_off(folder: Path) -> list[Company]:
    """scraper/companies.py as it is with its one setting turned off — what the owner's request changes."""
    source = (ROOT / "scraper" / "companies.py").read_text(encoding="utf-8")
    assert source.count("CONNECT_ENABLED = True") == 1
    copy = folder / "companies_switched_off.py"
    copy.write_text(source.replace("CONNECT_ENABLED = True", "CONNECT_ENABLED = False"), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("companies_switched_off", copy)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.COMPANIES


def test_the_one_setting_switches_connect_off_and_nothing_else(tmp_path: Path) -> None:
    listed = companies_with_connect_switched_off(tmp_path)
    assert [(c.id, c.enabled) for c in listed] == [(c.id, c.id != "connect") for c in companies.COMPANIES]


def test_switched_off_connect_is_not_asked_and_leaves_both_data_files(tmp_path: Path,
                                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    listed = [c for c in companies_with_connect_switched_off(tmp_path) if c.id in ("socar", "connect")]
    asked: list[str] = []

    def get(url: str) -> str:
        asked.append(url)
        return fixture("socar-stations.json" if url == socar.STATIONS_URL else "socar.html")

    out, places = tmp_path / "prices.json", tmp_path / "stations.json"
    out.write_text(json.dumps({"companies": [previous_prices()["connect"]]}), encoding="utf-8")
    places.write_text(json.dumps({"companies": [previous_stations()["connect"]]}), encoding="utf-8")
    monkeypatch.setattr(cli, "COMPANIES", listed)
    monkeypatch.setattr(cli, "fetch", get)
    assert cli.main(["--out", str(out), "--stations-out", str(places)]) == 0
    assert asked and not [u for u in asked if "connect.com.ge" in u]
    for path in (out, places):
        assert [e["id"] for e in json.loads(path.read_text(encoding="utf-8"))["companies"]] == ["socar"]


def test_switched_off_connect_says_so_once_for_each_data_file(tmp_path: Path) -> None:
    off = next(c for c in companies_with_connect_switched_off(tmp_path) if c.id == "connect")
    _p, log, _r = refresh([off], previous_prices(), lambda url: "", NOW)
    _s, places_log, _r = refresh_stations([off], previous_stations(), lambda url: "", NOW)
    assert log == ["Connect: switched off — not read, its prices removed"]
    assert places_log == ["Connect: switched off — not read, its stations removed"]
