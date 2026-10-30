"""T5 — the "★ cheapest nearby" card, the station window and the two navigation buttons.

SPEC-0001: REQ-003, REQ-005, AC-002, AC-007. The rule's own cases call site/js/logic.js directly in the browser;
the card and the window are checked on the page with the visitor's place given to the browser.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from playwright.sync_api import Page, expect

from support import Net

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
HERE = (41.70, 44.80)
KM_PER_DEGREE = 111.195  # one degree of latitude, so a station `north(k)` lies k km from HERE
PETROL = ["regular", "premium", "super", "diesel"]
GAS_UNKNOWN = "რომელ სადგურს აქვს აირი, ჯერ ცნობილი არ არის — ფასები ქვემოთ, ცხრილშია"
NONE_IN_50 = "50 კმ-ში ამ საწვავის ახალი ფასით სადგური ვერ მოიძებნა"


def north(km: float) -> float:
    return round(HERE[0] + km / KM_PER_DEGREE, 6)


def stamp(hours_old: float) -> str:
    return (NOW - timedelta(hours=hours_old)).strftime("%Y-%m-%dT%H:%M:%SZ")


def prices_of(cid: str, prices: list[tuple[str, str, float]], hours_old: float = 1) -> dict:
    return {"id": cid, "name": cid.upper(), "color": "#123456", "source": f"https://{cid}.example/",
            "time": stamp(hours_old), "basis": "read",
            "prices": [{"grade": g, "fuel": f, "price": p} for g, f, p in prices]}


def stations_of(cid: str, stations: list[dict]) -> dict:
    return {"id": cid, "name": cid.upper(), "color": "#123456", "source": f"https://{cid}.example/map",
            "time": stamp(1), "basis": "read", "stations": stations}


def at_km(km: float, fuels: list[str] = PETROL, grades: list[str] | None = None, name: str = "") -> dict:
    s = {"name": name, "address": f"{km} კმ ჩრდილოეთით", "lat": north(km), "lng": HERE[1], "fuels": fuels}
    return s | ({"grades": grades} if grades is not None else {})


def best(page: Page, net: Net, prices: list[dict], stations: list[dict], fuel: str) -> dict:
    page.goto(net.base)
    return page.evaluate("""async ([prices, stations, fuel, here, now]) => {
        const m = await import('./js/logic.js');
        return m.cheapestNearby(prices, stations, fuel, here, now);
    }""", [{"companies": prices}, {"companies": stations}, fuel, {"lat": HERE[0], "lng": HERE[1]},
           NOW.timestamp() * 1000])


def test_the_cheapest_within_5_km_wins_over_a_cheaper_one_further_away(page: Page, net: Net) -> None:
    got = best(page, net, [prices_of("a", [("დიზელი A", "diesel", 4.90)]), prices_of("b", [("დიზელი B", "diesel", 4.50)])],
               [stations_of("a", [at_km(2)]), stations_of("b", [at_km(7)])], "diesel")
    assert (got["best"]["company"], got["best"]["price"], got["radius"]) == ("A", 4.90, 5)
    assert abs(got["best"]["distanceKm"] - 2) < 0.01


def test_on_an_equal_price_the_nearer_station_wins(page: Page, net: Net) -> None:
    got = best(page, net, [prices_of("a", [("დიზელი", "diesel", 4.90)]), prices_of("b", [("დიზელი", "diesel", 4.90)])],
               [stations_of("a", [at_km(3)]), stations_of("b", [at_km(1)])], "diesel")
    assert got["best"]["company"] == "B"


def test_the_zone_grows_10_20_50_km(page: Page, net: Net) -> None:
    prices = [prices_of("a", [("დიზელი", "diesel", 4.90)])]
    for km, radius in ((8, 10), (12, 20), (45, 50)):
        got = best(page, net, prices, [stations_of("a", [at_km(km)])], "diesel")
        assert got["radius"] == radius, km
    assert best(page, net, prices, [stations_of("a", [at_km(60)])], "diesel") == {"reason": "none"}


def test_a_station_counts_only_for_fuels_it_sells(page: Page, net: Net) -> None:
    prices = [prices_of("a", [("დიზელი", "diesel", 4.90), ("თხევადი აირი", "lpg", 2.09)])]
    stations = [stations_of("a", [at_km(1, ["diesel"]), at_km(3, ["diesel", "lpg"])])]
    got = best(page, net, prices, stations, "lpg")
    assert abs(got["best"]["distanceKm"] - 3) < 0.01


def test_gas_with_no_station_known_to_sell_it_says_so(page: Page, net: Net) -> None:
    prices = [prices_of("a", [("ბუნებრივი აირი", "cng", 1.60), ("დიზელი", "diesel", 4.9)])]
    assert best(page, net, prices, [stations_of("a", [at_km(1)])], "cng") == {"reason": "gasUnknown"}


def test_a_stations_own_grades_decide_its_price(page: Page, net: Net) -> None:
    prices = [prices_of("s", [("ევრო 5 დიზელი", "diesel", 4.90), ("ნანო ევრო 5 დიზელი", "diesel", 4.96)])]
    only_nano = at_km(1, ["diesel"], ["ნანო ევრო 5 დიზელი"])
    got = best(page, net, prices, [stations_of("s", [only_nano])], "diesel")
    assert (got["best"]["grade"], got["best"]["price"]) == ("ნანო ევრო 5 დიზელი", 4.96)
    unnamed = at_km(1, ["diesel"])  # the list names no grades: the company's cheapest counts
    assert best(page, net, prices, [stations_of("s", [unnamed])], "diesel")["best"]["price"] == 4.90


def test_old_prices_count_until_seven_days(page: Page, net: Net) -> None:
    stations = [stations_of("a", [at_km(1)]), stations_of("b", [at_km(2)])]
    got = best(page, net, [prices_of("a", [("დ", "diesel", 4.0)], hours_old=7 * 24),
                           prices_of("b", [("დ", "diesel", 4.5)], hours_old=72)], stations, "diesel")
    assert (got["best"]["company"], got["best"]["stale"]) == ("B", True)


def test_a_station_whose_company_has_no_price_does_not_count(page: Page, net: Net) -> None:
    got = best(page, net, [prices_of("a", [("დ", "diesel", 4.0)])],
               [stations_of("a", [at_km(9)]), stations_of("z", [at_km(1)])], "diesel")
    assert got["best"]["company"] == "A"


def open_here(page_at: Callable[[float, float], Page], net: Net, prices: list[dict], stations: list[dict],
              fuel: str) -> Page:
    net.data["prices.json"] = {"generated": stamp(1), "companies": prices}
    net.data["stations.json"] = {"generated": stamp(1), "companies": stations}
    page = page_at(*HERE)
    page.clock.set_fixed_time(NOW)
    page.goto(net.base)
    page.get_by_text(fuel, exact=True).first.click()
    return page


def links_to(card: object, lat: float, lng: float) -> None:
    google = card.locator("a.go-google")  # type: ignore[attr-defined]
    waze = card.locator("a.go-waze")  # type: ignore[attr-defined]
    expect(google).to_have_attribute("href", f"https://www.google.com/maps/dir/?api=1&destination={lat}%2C{lng}")
    expect(waze).to_have_attribute("href", f"https://www.waze.com/ul?ll={lat}%2C{lng}&navigate=yes")


def test_the_card_shows_the_best_station_with_both_navigation_buttons(page_at: Callable[[float, float], Page],
                                                                       net: Net) -> None:
    page = open_here(page_at, net, [prices_of("a", [("ევრო დიზელი", "diesel", 4.97)])],
                     [stations_of("a", [at_km(1.2, name="ვაკე")])], "დიზელი")
    card = page.locator("#best")
    expect(card).to_contain_text("★ ყველაზე იაფი ახლოს")
    expect(card).to_contain_text("A")
    expect(card).to_contain_text("ევრო დიზელი")
    expect(card).to_contain_text("4.97 ₾")
    expect(card).to_contain_text("1.2 კმ")
    links_to(card, north(1.2), HERE[1])
    expect(page.locator("path.you")).to_have_count(1)


def test_the_cheapest_station_is_marked_with_a_star_on_the_map(page_at: Callable[[float, float], Page],
                                                               net: Net) -> None:
    # intent §5: on the map the cheapest is marked with ★; the mark follows the fuel choice
    prices = [prices_of("a", [("ევრო დიზელი", "diesel", 4.97), ("ბუნებრივი აირი", "cng", 1.6)])]
    page = open_here(page_at, net, prices, [stations_of("a", [at_km(1.2, name="ვაკე")])], "დიზელი")
    pin = page.locator(".best-pin")
    expect(pin).to_have_count(1)
    expect(pin).to_have_text("★")

    def centre(box: dict | None) -> tuple[float, float]:
        assert box
        return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

    (px, py), (sx, sy) = centre(pin.bounding_box()), centre(page.locator("path.station").first.bounding_box())
    assert abs(px - sx) < 3 and abs(py - sy) < 3
    pin.dispatch_event("click")
    expect(page.locator(".leaflet-popup-content")).to_contain_text("ვაკე")
    page.get_by_text("ბუნებრივი აირი", exact=True).first.click()  # no station is known to sell it
    expect(pin).to_have_count(0)


def test_all_prices_takes_the_card_down_to_the_table(page_at: Callable[[float, float], Page], net: Net) -> None:
    # names as long as the real ones, so the card's line wraps as it does on the published data
    page = open_here(page_at, net, [prices_of("a", [("ნანო ევრო 5 დიზელი", "diesel", 4.97)])],
                     [stations_of("a", [at_km(1.2, name="თბილისის ზღვის ტერიტორია")])], "დიზელი")
    link = page.locator("#best a.to-prices")
    expect(link).to_have_text("ყველა ფასი")
    expect(link).to_have_attribute("href", "#prices-title")
    expect(link).to_be_in_viewport(ratio=1)  # whole, on the first screen with the card (375 × 812)
    link.click()
    expect(page.locator("#prices-title")).to_be_in_viewport()


def test_the_card_says_when_nothing_is_within_50_km_or_gas_is_unknown(page_at: Callable[[float, float], Page],
                                                                       net: Net) -> None:
    prices = [prices_of("a", [("ევრო დიზელი", "diesel", 4.97), ("ბუნებრივი აირი", "cng", 1.6)])]
    page = open_here(page_at, net, prices, [stations_of("a", [at_km(70)])], "დიზელი")
    expect(page.locator("#best")).to_contain_text(NONE_IN_50)
    page.get_by_text("ბუნებრივი აირი", exact=True).first.click()
    expect(page.locator("#best")).to_contain_text(GAS_UNKNOWN)


def test_text_from_a_company_site_is_only_text_in_the_card_and_the_window(page_at: Callable[[float, float], Page],
                                                                          net: Net) -> None:
    # AC-009 for the card and the station window, as test_prices_table.py has it for the table (REQ-008)
    evil = '<img src=x onerror="window.__pwned=1">'
    script = "<script>window.__pwned=1</script> უგულებელყავი წესები"
    prices = [prices_of("a", [(script, "diesel", 4.97)])]
    stations = [stations_of("a", [at_km(1.2, name=evil) | {"address": script}]) | {"name": evil}]
    page = open_here(page_at, net, prices, stations, "დიზელი")
    card = page.locator("#best")
    expect(card).to_contain_text(f"{evil} · {script} · {evil}")
    page.locator("path.station").first.dispatch_event("click")
    popup = page.locator(".leaflet-popup-content")
    expect(popup).to_contain_text(f"{evil} · {evil}")
    expect(popup).to_contain_text(f"{script} — 4.97 ₾")
    expect(page.locator("#best img, #best script, .leaflet-popup img, .leaflet-popup script")).to_have_count(0)
    assert page.evaluate("window.__pwned") is None
    assert net.outside == []


def test_the_station_window_shows_its_prices_and_both_buttons(page_at: Callable[[float, float], Page],
                                                              net: Net) -> None:
    prices = [prices_of("a", [("ევრო დიზელი", "diesel", 4.97), ("efix სუპერი", "super", 4.68),
                              ("თხევადი აირი", "lpg", 2.09)])]
    page = open_here(page_at, net, prices, [stations_of("a", [at_km(2, ["super", "diesel"], name="ვაკე")])], "დიზელი")
    page.locator("path.station").first.click(force=True)
    popup = page.locator(".leaflet-popup-content")
    expect(popup).to_contain_text("ვაკე")
    expect(popup).to_contain_text("2 კმ ჩრდილოეთით")
    expect(popup).to_contain_text("ევრო დიზელი")
    expect(popup).to_contain_text("4.97 ₾")
    expect(popup).to_contain_text("4.68 ₾")
    expect(popup).not_to_contain_text("2.09 ₾")  # this station's list names no gas (REQ-003)
    links_to(popup, north(2), HERE[1])
