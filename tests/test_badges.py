"""SPEC-0002 — the company badges above the ★ card, and the row as the company filter.

PLAN-0002 T2: one badge per company in the data, in its colour with its name, as text only (REQ-001, REQ-007;
AC-001, AC-009, AC-010, AC-011).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from playwright.sync_api import Page, expect

from support import SITE, TILE_HOST, Net

TIME = "2026-10-30T12:00:00Z"
REAL = [("socar", "SOCAR", "#e41e30"), ("rompetrol", "Rompetrol", "#f39200"), ("lukoil", "Lukoil", "#8a1538"),
        ("wissol", "Wissol", "#00843d")]  # the colours the reader writes (PLAN-0001 T3 — a hypothesis)
BADGES = "#companies button.badge"
PICTURES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif", ".ico")


def prices_of(cid: str, name: str, color: str, **extra: object) -> dict:
    return {"id": cid, "name": name, "color": color, "source": f"https://{cid}.example/", "time": TIME,
            "basis": "read", "prices": [{"grade": "დიზელი", "fuel": "diesel", "price": 4.9}], **extra}


def stations_of(cid: str, name: str, color: str) -> dict:
    return {"id": cid, "name": name, "color": color, "source": f"https://{cid}.example/map", "time": TIME,
            "basis": "read", "stations": [{"name": "", "address": "a", "lat": 41.7, "lng": 44.8,
                                           "fuels": ["diesel"]}]}


def open_with(page: Page, net: Net, prices: list[dict], stations: list[dict] | None = None) -> None:
    net.data["prices.json"] = {"generated": TIME, "companies": prices}
    net.data["stations.json"] = {"generated": TIME, "companies": stations or []}
    page.goto(net.base)


def rgb(hex_color: str) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgb({r}, {g}, {b})"


def test_one_badge_per_company_in_its_colour_with_its_name(page: Page, net: Net) -> None:
    open_with(page, net, [prices_of(*c) for c in REAL])
    badges = page.locator(BADGES)
    expect(badges).to_have_text([name for _, name, _ in REAL])
    for i, (_, _, color) in enumerate(REAL):
        expect(badges.nth(i)).to_have_attribute("aria-pressed", "true")  # all on at the start
        assert badges.nth(i).evaluate("b => getComputedStyle(b).backgroundColor") == rgb(color)
    expect(page.locator("#companies")).to_have_attribute("aria-label", "კომპანიები")
    page.get_by_role("button", name="ENG").click()
    expect(page.locator("#companies")).to_have_attribute("aria-label", "Companies")


def test_the_row_follows_the_data_and_stands_above_the_card(page: Page, net: Net) -> None:
    # a company with stations only counts; one without a source is shown nowhere (SPEC-0001 REQ-006)
    nameless_source = prices_of("x", "NoSource", "#123456")
    del nameless_source["source"]
    open_with(page, net, [prices_of("a", "Alpha", "#e41e30"), prices_of("b", "Beta", "#00843d"), nameless_source],
              stations=[stations_of("a", "Alpha", "#e41e30"), stations_of("c", "Gamma", "#8a1538")])
    expect(page.locator(BADGES)).to_have_text(["Alpha", "Beta", "Gamma"])
    expect(page.locator("#best")).to_be_visible()  # no place was allowed: the card asks for a city
    row, card = page.locator("#companies").bounding_box(), page.locator("#best").bounding_box()
    assert row and card and row["y"] + row["height"] <= card["y"]


def test_the_letters_colour_is_the_one_that_reads_best_on_the_badge(page: Page, net: Net) -> None:
    # REQ-007: white on SOCAR's red, Lukoil's crimson and Wissol's green; dark on Rompetrol's orange
    open_with(page, net, [prices_of(*c) for c in REAL])
    inks = [b.evaluate("b => getComputedStyle(b).color") for b in page.locator(BADGES).all()]
    assert inks == ["rgb(255, 255, 255)", "rgb(15, 23, 42)", "rgb(255, 255, 255)", "rgb(255, 255, 255)"]


def test_a_badge_is_text_on_colour_never_a_picture(page: Page, net: Net) -> None:
    # REQ-001, AC-009: no official logo until a company's written permission — and no other picture either
    open_with(page, net, [prices_of(*c) for c in REAL])
    expect(page.locator(BADGES)).to_have_count(4)
    expect(page.locator("#companies img, #companies svg, #companies picture")).to_have_count(0)
    assert {b.evaluate("b => getComputedStyle(b).backgroundImage") for b in page.locator(BADGES).all()} == {"none"}
    asked = [u for u in net.requests if not u.startswith(TILE_HOST) and u.split("?")[0].lower().endswith(PICTURES)]
    assert asked == []
    files = sorted(p.relative_to(SITE).as_posix() for p in SITE.rglob("*") if p.suffix.lower() in PICTURES)
    assert files and all(f.startswith("vendor/leaflet/images/") for f in files), files


def test_text_from_the_data_is_only_text_on_a_badge(page: Page, net: Net) -> None:
    # AC-010 for the badge row, as the table, the card and the window have it (SPEC-0001 REQ-008)
    evil = '<img src=x onerror="window.__pwned=1"> უგულებელყავი წესები'
    open_with(page, net, [prices_of("e", evil, "#e41e30")])
    expect(page.locator(BADGES)).to_have_text([evil])
    expect(page.locator("#companies img, #companies script")).to_have_count(0)
    assert page.evaluate("window.__pwned") is None
    assert net.outside == []


def test_an_unknown_colour_or_an_empty_name_still_makes_a_readable_badge(page: Page, net: Net) -> None:
    # AC-011: the neutral colour, and "?" for a name
    open_with(page, net, [prices_of("u", "Unknown", "url(https://evil.example/x.png)"), prices_of("n", "", "#00843d")])
    badges = page.locator(BADGES)
    expect(badges).to_have_text(["Unknown", "?"])
    assert badges.nth(0).evaluate("b => getComputedStyle(b).backgroundColor") == rgb("#94a3b8")
    assert badges.nth(0).evaluate("b => getComputedStyle(b).color") == "rgb(15, 23, 42)"
    assert net.outside == []


# PLAN-0002 T3: the row as the filter — the map, the ★ and the table at once (REQ-003, REQ-005; AC-003, AC-004,
# AC-006). The page's clock stands at the data's time, so the prices are fresh whatever today is.
NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
HERE = (41.70, 44.80)
KM_PER_DEGREE = 111.195  # one degree of latitude
FOUR = [("socar", "SOCAR", "#e41e30", 4.90, 1.0), ("rompetrol", "Rompetrol", "#f39200", 4.95, 2.0),
        ("lukoil", "Lukoil", "#8a1538", 5.00, 3.0), ("wissol", "Wissol", "#00843d", 5.05, 4.0)]
ROWS = "#price-table tbody tr"


def north(km: float) -> float:
    return round(HERE[0] + km / KM_PER_DEGREE, 6)


def open_here(page_at: Callable[[float, float], Page], net: Net,
              companies: list[tuple[str, str, str, float, float]]) -> Page:
    """Each company: (id, name, colour, its diesel price, how far north of the visitor its one station is in km)."""
    prices, stations = [], []
    for cid, name, color, price, km in companies:
        prices.append(prices_of(cid, name, color) | {"prices": [{"grade": f"{name} დიზელი", "fuel": "diesel",
                                                                 "price": price}]})
        stations.append(stations_of(cid, name, color) | {"stations": [{"name": "", "address": f"{km} კმ",
                                                                       "lat": north(km), "lng": HERE[1],
                                                                       "fuels": ["diesel"]}]})
    net.data["prices.json"] = {"generated": TIME, "companies": prices}
    net.data["stations.json"] = {"generated": TIME, "companies": stations}
    page = page_at(*HERE)
    page.clock.set_fixed_time(NOW)
    page.goto(net.base)
    page.get_by_text("დიზელი", exact=True).first.click()
    return page


def circles_of(page: Page, cid: str) -> object:
    return page.locator(f'.station[data-company="{cid}"]')


def centre(box: dict | None) -> tuple[float, float]:
    assert box
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def test_a_badge_switches_its_company_off_and_on_everywhere(page_at: Callable[[float, float], Page],
                                                            net: Net) -> None:
    page = open_here(page_at, net, FOUR)
    rompetrol = page.locator(BADGES).nth(1)
    expect(circles_of(page, "rompetrol")).to_have_count(1)  # type: ignore[attr-defined]
    expect(page.locator(ROWS)).to_have_count(4)
    rompetrol.click()
    expect(rompetrol).to_have_attribute("aria-pressed", "false")
    assert rompetrol.evaluate("b => getComputedStyle(b).backgroundColor") == "rgba(0, 0, 0, 0)"  # only the frame
    assert rompetrol.evaluate("b => getComputedStyle(b).textDecorationLine") == "line-through"
    expect(circles_of(page, "rompetrol")).to_have_count(0)  # type: ignore[attr-defined]
    expect(page.locator(ROWS)).to_have_count(3)
    expect(page.locator("#price-table")).not_to_contain_text("Rompetrol")
    rompetrol.click()
    expect(rompetrol).to_have_attribute("aria-pressed", "true")
    expect(circles_of(page, "rompetrol")).to_have_count(1)  # type: ignore[attr-defined]
    expect(page.locator(ROWS)).to_have_count(4)


def test_the_star_moves_to_the_cheapest_company_still_on(page_at: Callable[[float, float], Page], net: Net) -> None:
    # Gamma is the cheapest of all, but 15 km away: the ★ reaches it only when nothing nearer is on
    page = open_here(page_at, net, [("a", "Alpha", "#e41e30", 4.80, 1.0), ("b", "Beta", "#00843d", 4.95, 3.0),
                                    ("g", "Gamma", "#8a1538", 4.70, 15.0)])
    card, alpha, beta = page.locator("#best"), page.locator(BADGES).nth(0), page.locator(BADGES).nth(1)
    expect(card).to_contain_text("Alpha")
    alpha.click()
    expect(card).to_contain_text("Beta")
    (px, py), (sx, sy) = centre(page.locator(".best-pin").bounding_box()), centre(
        circles_of(page, "b").bounding_box())  # type: ignore[attr-defined]
    assert abs(px - sx) < 3 and abs(py - sy) < 3  # the ★ on the map moved with the card
    beta.click()
    expect(card).to_contain_text("Gamma")
    expect(card).to_contain_text("15.0 კმ")  # nothing on within 5 or 10 km: the zone grew to 20 km
    alpha.click()
    expect(card).to_contain_text("Alpha")


def test_with_every_company_off_the_page_says_to_turn_one_on(page_at: Callable[[float, float], Page],
                                                             net: Net) -> None:
    page = open_here(page_at, net, FOUR)
    for badge in page.locator(BADGES).all():
        badge.click()
    expect(page.locator(".station")).to_have_count(0)
    expect(page.locator(".best-pin")).to_have_count(0)
    expect(page.locator("#best")).to_contain_text("ჩართე ერთი კომპანია მაინც")
    expect(page.locator(ROWS)).to_have_count(0)
    expect(page.locator("#status")).to_contain_text("ჩართე ერთი კომპანია მაინც")
    page.get_by_role("button", name="ENG").click()
    expect(page.locator("#best")).to_contain_text("Turn on at least one company")
    expect(page.locator("#status")).to_contain_text("Turn on at least one company")
    page.locator(BADGES).first.click()  # SOCAR on again
    expect(circles_of(page, "socar")).to_have_count(1)  # type: ignore[attr-defined]
    expect(page.locator(ROWS)).to_have_count(1)


# PLAN-0002 T4: when the filter took the fuel away, the card and the table say so (REQ-006; AC-007)
FILTERED_KA = "ჩართულ კომპანიებში ამ საწვავის ფასი არ მოიძებნა — ჩართე სხვა კომპანიაც"
FILTERED_EN = "No price for this fuel among the companies switched on — turn on another company"
GAS_UNKNOWN_KA = "ფასები ქვემოთ, ცხრილშია"


def test_when_only_a_switched_off_company_has_the_fuel_the_page_says_so(page_at: Callable[[float, float], Page],
                                                                        net: Net) -> None:
    # Gas: today only SOCAR publishes its price ([[fuel-price-sources]]); SOCAR off and gas chosen
    page = open_here(page_at, net, [("socar", "SOCAR", "#e41e30", 4.90, 1.0), ("rompetrol", "Rompetrol", "#f39200",
                                                                                4.95, 2.0)])
    socar = net.data["prices.json"]["companies"][0]  # type: ignore[index]
    socar["prices"].append({"grade": "SOCAR თხევადი აირი", "fuel": "lpg", "price": 2.09})
    net.data["stations.json"]["companies"][0]["stations"][0]["fuels"].append("lpg")  # type: ignore[index]
    page.reload()
    page.locator(BADGES).nth(0).click()
    page.get_by_text("თხევადი აირი", exact=True).first.click()
    expect(page.locator("#best")).to_contain_text(FILTERED_KA)
    expect(page.locator("#best")).not_to_contain_text(GAS_UNKNOWN_KA)
    expect(page.locator(ROWS)).to_have_count(0)
    expect(page.locator("#status")).to_contain_text(FILTERED_KA)
    page.get_by_role("button", name="ENG").click()
    expect(page.locator("#best")).to_contain_text(FILTERED_EN)
    expect(page.locator("#status")).to_contain_text(FILTERED_EN)
    page.locator(BADGES).nth(0).click()  # SOCAR on again: the gas is back
    expect(page.locator(ROWS)).to_have_count(1)


def test_when_only_a_switched_off_company_is_near_the_card_says_so(page_at: Callable[[float, float], Page],
                                                                   net: Net) -> None:
    page = open_here(page_at, net, [("a", "Alpha", "#e41e30", 4.80, 70.0), ("b", "Beta", "#00843d", 4.95, 2.0)])
    expect(page.locator("#best")).to_contain_text("Beta")
    page.locator(BADGES).nth(1).click()
    expect(page.locator("#best")).to_contain_text(FILTERED_KA)  # Alpha is 70 km away; Beta, switched off, is near
    expect(page.locator(ROWS)).to_have_count(1)  # Alpha's price itself is still in the table


def test_a_gas_price_whose_stations_are_unknown_is_also_told_apart(page_at: Callable[[float, float], Page],
                                                                   net: Net) -> None:
    # SOCAR publishes a gas price but no station of it lists gas: with SOCAR on the card says "see the table",
    # with SOCAR off the table is empty — so the card must not send the visitor there
    page = open_here(page_at, net, [("socar", "SOCAR", "#e41e30", 4.90, 1.0), ("rompetrol", "Rompetrol", "#f39200",
                                                                                4.95, 2.0)])
    socar = net.data["prices.json"]["companies"][0]  # type: ignore[index]
    socar["prices"].append({"grade": "SOCAR თხევადი აირი", "fuel": "lpg", "price": 2.09})
    page.reload()
    page.get_by_text("თხევადი აირი", exact=True).first.click()
    expect(page.locator("#best")).to_contain_text(GAS_UNKNOWN_KA)
    page.locator(BADGES).nth(0).click()
    expect(page.locator("#best")).to_contain_text(FILTERED_KA)
    expect(page.locator("#best")).not_to_contain_text(GAS_UNKNOWN_KA)


# PLAN-0002 T5: the choice stays on the phone — only the companies switched off (REQ-004; AC-005, AC-011)
STORED_OFF = "localStorage.getItem('fuel-map.off')"
STORAGE_KA = "ენა და კომპანიების არჩევანი მხოლოდ შენს ტელეფონში ინახება"
STORAGE_EN = "The language and the companies you choose are kept only on your phone"


def reopen(page: Page) -> None:
    """The page opened again: the badges come with the data, and the fuel is the first one again."""
    page.reload()
    expect(page.locator(BADGES)).to_have_count(4)
    page.get_by_text("დიზელი", exact=True).first.click()


def test_the_choice_is_remembered_on_the_phone_and_nowhere_else(page_at: Callable[[float, float], Page],
                                                                 net: Net) -> None:
    page = open_here(page_at, net, FOUR)
    assert page.evaluate(STORED_OFF) is None  # everything on: nothing stored
    page.locator(BADGES).nth(1).click()
    page.locator(BADGES).nth(2).click()
    assert json.loads(page.evaluate(STORED_OFF)) == ["rompetrol", "lukoil"]
    assert set(page.evaluate("Object.keys(localStorage)")) == {"fuel-map.off"}
    assert page.context.cookies() == []
    reopen(page)
    pressed = [b.get_attribute("aria-pressed") for b in page.locator(BADGES).all()]
    assert pressed == ["true", "false", "false", "true"]
    expect(page.locator(ROWS)).to_have_count(2)
    assert not [u for u in net.requests if "rompetrol" in u or "lukoil" in u] and net.bodies == []
    page.locator(BADGES).nth(1).click()
    page.locator(BADGES).nth(2).click()
    assert page.evaluate(STORED_OFF) is None  # all on again: the list is gone
    expect(page.locator("footer")).to_contain_text(STORAGE_KA)
    page.get_by_role("button", name="ENG").click()
    expect(page.locator("footer")).to_contain_text(STORAGE_EN)


def test_a_broken_or_blocked_store_leaves_every_company_on(page_at: Callable[[float, float], Page],
                                                           net: Net) -> None:
    page = open_here(page_at, net, FOUR)
    for stored in ('{not json', '"rompetrol"', '[42, null]', '["ghost"]'):  # broken, not a list, not names, gone
        page.evaluate("v => localStorage.setItem('fuel-map.off', v)", stored)
        reopen(page)
        pressed = {b.get_attribute("aria-pressed") for b in page.locator(BADGES).all()}
        assert pressed == {"true"}, stored
        expect(page.locator(ROWS)).to_have_count(4)
    page.add_init_script("Storage.prototype.getItem = Storage.prototype.setItem = Storage.prototype.removeItem ="
                         " () => { throw new Error('blocked'); };")
    reopen(page)
    page.locator(BADGES).nth(0).click()  # the choice works for this visit, it just is not kept
    expect(page.locator(BADGES).nth(0)).to_have_attribute("aria-pressed", "false")
    expect(page.locator(ROWS)).to_have_count(3)


# PLAN-0002 T6: from the city view on, a station shows its company's first letter on its colour (REQ-002; AC-002)


def test_from_the_city_view_a_station_shows_its_companys_letter(page_at: Callable[[float, float], Page],
                                                                 net: Net) -> None:
    page = open_here(page_at, net, FOUR)  # the visitor's place: the city view
    for cid, name, color, _, _ in FOUR:
        mark = page.locator(f'.station[data-company="{cid}"] span')
        expect(mark).to_have_text(name[0])
        box = mark.bounding_box()
        assert box and box["width"] >= 20 and box["height"] >= 20, (cid, box)
        assert mark.evaluate("s => getComputedStyle(s).backgroundColor") == rgb(color)
        assert mark.evaluate("s => parseFloat(getComputedStyle(s).fontSize)") >= 11
    page.locator('.station[data-company="lukoil"]').dispatch_event("click")
    expect(page.locator(".leaflet-popup-content")).to_contain_text("Lukoil")  # the full name in the window


def test_from_far_a_station_is_a_small_dot_until_the_city_view(page: Page, net: Net) -> None:
    open_with(page, net, [prices_of("socar", "SOCAR", "#e41e30")], stations=[stations_of("socar", "SOCAR", "#e41e30")])
    page.get_by_text("დიზელი", exact=True).first.click()  # the station sells diesel only
    mark = page.locator(".station span")
    expect(mark).to_have_count(1)  # no place was allowed: the whole of Georgia is in view
    expect(mark).to_have_text("")
    box = mark.bounding_box()
    assert box and box["width"] < 20
    zoom_in, zoom_out = page.locator(".leaflet-control-zoom-in"), page.locator(".leaflet-control-zoom-out")
    for _ in range(5):  # by hand, as with the fingers: from the whole country to the city view
        zoom_in.click()
        page.wait_for_timeout(350)  # Leaflet's zoom animation
    expect(mark).to_have_text("S")
    for _ in range(5):
        zoom_out.click()
        page.wait_for_timeout(350)
    expect(mark).to_have_text("")


# PLAN-0002 T7: the badges on a phone, by day and at night (REQ-007; AC-008)
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_badges_fit_a_phone_by_day_and_at_night(page_at: Callable[[float, float], Page], net: Net,
                                                    scheme: str) -> None:
    page = page_at(*HERE)
    page.emulate_media(color_scheme=scheme)
    net.data["prices.json"] = {"generated": TIME, "companies": [prices_of(*c) for c in REAL]}
    page.goto(net.base)
    badges = page.locator(BADGES)
    expect(badges).to_have_count(4)
    badges.nth(1).click()  # one switched off: its size must not change
    for badge in badges.all():
        box = badge.bounding_box()
        assert box and box["width"] >= 44 and box["height"] >= 44, box  # a finger's size
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")  # the row scrolls, not the page
