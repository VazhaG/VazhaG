"""SPEC-0003 on the page — Connect as the fifth company (PLAN-0003 T4–T6).

T4: a company whose colour is light (its letters are dark: today Rompetrol and Connect) has a dark outline by day, on
its badge and on its map circles, so they stand out on the white page and the light map; at night the outline is as
before (REQ-003; AC-007).
T5: five badges do not fit a phone's width — the row scrolls in its place, never the page, and the edge with more
badges beyond it fades in a 24 px strip; a badge reached from the keyboard stops clear of the strip (REQ-005; AC-006).
T6: Connect works on the page as every other company — its badge and letter, the switch, the ★ with both route links,
the gas fuels, a returning visitor's stored choice (REQ-003; AC-005).
"""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from playwright.sync_api import Page, expect

from support import Net

TIME = "2026-10-31T12:00:00Z"
HERE = (41.70, 44.80)
KM_PER_DEGREE = 111.195  # one degree of latitude
# (id, name, colour the reader writes, its diesel price, how far north of the visitor its one station is in km)
FIVE = [("socar", "SOCAR", "#e41e30", 4.90, 1.0), ("rompetrol", "Rompetrol", "#f39200", 4.95, 2.0),
        ("lukoil", "Lukoil", "#8a1538", 5.00, 3.0), ("wissol", "Wissol", "#00843d", 5.05, 4.0),
        ("connect", "Connect", "#ffe900", 4.80, 4.5)]
LIGHT = {"rompetrol", "connect"}  # the companies whose letters are dark (SPEC-0002 REQ-007)
DARK_INK, WHITE = (15, 23, 42), (255, 255, 255)
NIGHT_PAGE = (11, 18, 32)  # #0b1220, the page at night — the map's tiles are darkened to it (AC-007)
BACKGROUND_JS = """(el) => {
  for (; el; el = el.parentElement) {
    const c = getComputedStyle(el).backgroundColor.match(/[\\d.]+/g).map(Number);
    if (c.length < 4 || c[3] > 0) return 'rgb(' + c.slice(0, 3).join(', ') + ')';
  }
  return 'rgb(255, 255, 255)';
}"""


def north(km: float) -> float:
    return round(HERE[0] + km / KM_PER_DEGREE, 6)


def open_five(page_at: Callable[[float, float], Page], net: Net, scheme: str = "light") -> Page:
    prices, stations = [], []
    for cid, name, color, price, km in FIVE:
        head = {"id": cid, "name": name, "color": color, "source": f"https://{cid}.example/", "time": TIME,
                "basis": "read"}
        prices.append(head | {"prices": [{"grade": f"{name} დიზელი", "fuel": "diesel", "price": price}]})
        stations.append(head | {"stations": [{"name": "", "address": f"{km} კმ", "lat": north(km), "lng": HERE[1],
                                              "fuels": ["regular", "premium", "super", "diesel"]}]})
    net.data["prices.json"] = {"generated": TIME, "companies": prices}
    net.data["stations.json"] = {"generated": TIME, "companies": stations}
    page = page_at(*HERE)
    page.emulate_media(color_scheme=scheme)
    page.clock.set_fixed_time(TIME)
    page.goto(net.base)
    page.get_by_text("დიზელი", exact=True).first.click()
    expect(page.locator(".station.near span")).to_have_count(len(FIVE))  # the city view: letters on the map
    return page


def rgb(text: str) -> tuple[int, ...]:
    return tuple(int(float(v)) for v in text[text.index("(") + 1:text.index(")")].split(",")[:3])


def hex_rgb(color: str) -> tuple[int, ...]:
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def ratio(a: tuple[int, ...], b: tuple[int, ...]) -> float:
    def lum(c: tuple[int, ...]) -> float:
        parts = [v / 255 for v in c]
        parts = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in parts]
        return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]

    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def style(page: Page, selector: str, prop: str) -> tuple[int, ...]:
    return rgb(page.locator(selector).first.evaluate(f"el => getComputedStyle(el).{prop}"))


def badge(cid: str) -> str:
    return f'#companies [data-company="{cid}"]'


def circle(cid: str) -> str:
    return f'.station[data-company="{cid}"] span'


def test_by_day_a_light_colour_has_a_dark_outline_on_its_badge_and_its_circles(
        page_at: Callable[[float, float], Page], net: Net) -> None:
    page = open_five(page_at, net, "light")
    for cid, _, color, _, _ in FIVE:
        light = cid in LIGHT
        assert style(page, badge(cid), "borderTopColor") == (DARK_INK if light else hex_rgb(color)), cid
        assert style(page, circle(cid), "borderTopColor") == (DARK_INK if light else WHITE), cid
    page.locator(badge("connect")).click()  # switched off: only the frame stays — still dark
    expect(page.locator(badge("connect"))).to_have_attribute("aria-pressed", "false")
    assert style(page, badge("connect"), "borderTopColor") == DARK_INK


def test_at_night_the_outline_is_as_before(page_at: Callable[[float, float], Page], net: Net) -> None:
    page = open_five(page_at, net, "dark")
    for cid, _, color, _, _ in FIVE:
        assert style(page, badge(cid), "borderTopColor") == hex_rgb(color), cid
        assert style(page, circle(cid), "borderTopColor") == WHITE, cid


@pytest.mark.parametrize(("scheme", "ground"), [("light", WHITE), ("dark", NIGHT_PAGE)])
def test_every_companys_circle_stands_out_from_the_map(page_at: Callable[[float, float], Page], net: Net,
                                                       scheme: str, ground: tuple[int, ...]) -> None:
    # AC-007: the circle's fill or its outline has at least 3 : 1 against the map
    page = open_five(page_at, net, scheme)
    for cid, *_ in FIVE:
        fill, edge = style(page, circle(cid), "backgroundColor"), style(page, circle(cid), "borderTopColor")
        assert max(ratio(fill, ground), ratio(edge, ground)) >= 3, (cid, fill, edge)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_connects_name_and_letter_read_well_on_and_off(page_at: Callable[[float, float], Page], net: Net,
                                                       scheme: str) -> None:
    page = open_five(page_at, net, scheme)
    letter = page.locator(circle("connect"))
    expect(letter).to_have_text("C")
    assert ratio(style(page, circle("connect"), "color"), style(page, circle("connect"), "backgroundColor")) >= 4.5
    on = page.locator(badge("connect"))
    assert ratio(rgb(on.evaluate("b => getComputedStyle(b).color")), rgb(on.evaluate(BACKGROUND_JS))) >= 4.5
    on.click()
    expect(on).to_have_attribute("aria-pressed", "false")
    assert ratio(rgb(on.evaluate("b => getComputedStyle(b).color")), rgb(on.evaluate(BACKGROUND_JS))) >= 4.5


# T5 — the row of five (REQ-005; AC-006)
STRIP = 24  # px — the faded strip at an edge with more badges beyond it (a hypothesis the owner approved)
ROW = "#companies"
EDGES_JS = """(row) => {
  const mask = getComputedStyle(row).maskImage || getComputedStyle(row).webkitMaskImage || 'none';
  return { more: row.scrollWidth > row.clientWidth, start: row.classList.contains('more-start'),
           end: row.classList.contains('more-end'), mask };
}"""


def edges(page: Page) -> dict:
    return page.locator(ROW).evaluate(EDGES_JS)


def scroll_row(page: Page, to: str) -> None:
    page.locator(ROW).evaluate(f"(row) => {{ row.scrollLeft = {'row.scrollWidth' if to == 'end' else 0}; }}")
    page.wait_for_timeout(100)  # the scroll event


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("language", ["ka", "en"])
def test_five_badges_scroll_in_their_row_never_the_page_and_the_edge_beyond_fades(
        page_at: Callable[[float, float], Page], net: Net, scheme: str, language: str) -> None:
    page = open_five(page_at, net, scheme)
    if language == "en":
        page.get_by_role("button", name="ENG").click()
        expect(page.locator(ROW)).to_have_attribute("aria-label", "Companies")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    at_start = edges(page)
    assert at_start["more"] and at_start["end"] and not at_start["start"], at_start
    assert "linear-gradient" in at_start["mask"] and f"{STRIP}px" in at_start["mask"], at_start
    scroll_row(page, "end")
    at_end = edges(page)
    assert at_end["start"] and not at_end["end"], at_end
    last, row = page.locator(f"{ROW} .badge").last.bounding_box(), page.locator(ROW).bounding_box()
    assert last and row and last["x"] + last["width"] <= row["x"] + row["width"] + 0.5  # the last badge fully in
    page.locator(f"{ROW} .badge").last.click()  # a finger reaches it
    expect(page.locator(f"{ROW} .badge").last).to_have_attribute("aria-pressed", "false")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_a_row_that_fits_has_no_faded_edge(page_at: Callable[[float, float], Page], net: Net) -> None:
    net.data["prices.json"] = {"generated": TIME, "companies": [
        {"id": "a", "name": "Alpha", "color": "#e41e30", "source": "https://a.example/", "time": TIME,
         "basis": "read", "prices": [{"grade": "დიზელი", "fuel": "diesel", "price": 4.9}]}]}
    net.data["stations.json"] = {"generated": TIME, "companies": []}
    page = page_at(*HERE)
    page.clock.set_fixed_time(TIME)
    page.goto(net.base)
    expect(page.locator(f"{ROW} .badge")).to_have_count(1)
    state = edges(page)
    assert not state["more"] and not state["start"] and not state["end"] and state["mask"] == "none", state


def test_a_wider_screen_that_fits_the_row_loses_the_faded_edge(page_at: Callable[[float, float], Page],
                                                                net: Net) -> None:
    page = open_five(page_at, net)
    assert edges(page)["end"]
    page.set_viewport_size({"width": 1024, "height": 812})  # a phone turned sideways, a tablet
    page.wait_for_timeout(200)
    state = edges(page)
    assert not state["more"] and not state["start"] and not state["end"] and state["mask"] == "none", state


def test_every_badge_is_reached_and_pressed_from_the_keyboard_clear_of_the_strip(
        page_at: Callable[[float, float], Page], net: Net) -> None:
    page = open_five(page_at, net)
    page.locator(f"{ROW} .badge").first.focus()
    for i, (cid, *_) in enumerate(FIVE):
        if i:
            page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement.dataset.company") == cid
        page.wait_for_timeout(100)  # the scroll that brings it into view, and its event
        state, row = edges(page), page.locator(ROW).bounding_box()
        box = page.locator(badge(cid)).bounding_box()
        assert row and box
        left = row["x"] + (STRIP if state["start"] else 0)
        right = row["x"] + row["width"] - (STRIP if state["end"] else 0)
        assert left - 0.5 <= box["x"] and box["x"] + box["width"] <= right + 0.5, (cid, state, box, row)
        page.keyboard.press("Space")
        expect(page.locator(badge(cid))).to_have_attribute("aria-pressed", "false")
        page.keyboard.press("Space")
        expect(page.locator(badge(cid))).to_have_attribute("aria-pressed", "true")


def test_with_five_badges_the_card_and_its_all_prices_link_stay_on_the_first_screen(
        page_at: Callable[[float, float], Page], net: Net) -> None:
    page = open_five(page_at, net)
    for target in ("#best", "#best a.to-prices"):
        box = page.locator(target).bounding_box()
        assert box and box["y"] + box["height"] <= 812, (target, box)


# T6 — Connect on the page, as every other company (REQ-003; AC-005). The page already does this for any company,
# so these pass at once; seeded defects prove they bite (PLAN-0003, deviations).
ROWS = "#price-table tbody tr"
STORED_OFF = "localStorage.getItem('fuel-map.off')"


def test_connects_badge_and_map_letter_in_its_colour_with_dark_letters(page_at: Callable[[float, float], Page],
                                                                       net: Net) -> None:
    page = open_five(page_at, net)
    expect(page.locator(f"{ROW} .badge")).to_have_text([name for _, name, *_ in FIVE])
    assert style(page, badge("connect"), "backgroundColor") == hex_rgb("#ffe900")
    assert style(page, badge("connect"), "color") == DARK_INK
    expect(page.locator(circle("connect"))).to_have_text("C")
    assert style(page, circle("connect"), "backgroundColor") == hex_rgb("#ffe900")
    assert style(page, circle("connect"), "color") == DARK_INK


def test_the_star_finds_connect_when_it_is_the_cheapest_near_with_both_route_links(
        page_at: Callable[[float, float], Page], net: Net) -> None:
    page = open_five(page_at, net)  # Connect's diesel is the cheapest within 5 km: 4.80 ₾ at 4.5 km
    best = page.locator("#best")
    expect(best.locator(".who strong")).to_have_text("Connect")
    expect(best.locator(".price")).to_contain_text("4.80")
    place = f"{north(4.5)}%2C{HERE[1]}"
    assert place in (best.locator("a.go-google").get_attribute("href") or "")
    assert place in (best.locator("a.go-waze").get_attribute("href") or "")


def test_switching_connect_off_and_on_changes_the_map_the_star_and_the_table(
        page_at: Callable[[float, float], Page], net: Net) -> None:
    page = open_five(page_at, net)
    expect(page.locator(ROWS)).to_have_count(5)
    page.locator(badge("connect")).click()
    expect(page.locator(circle("connect"))).to_have_count(0)
    expect(page.locator("#best .who strong")).to_have_text("SOCAR")  # the next cheapest within 5 km
    expect(page.locator(ROWS)).to_have_count(4)
    expect(page.locator(ROWS).filter(has_text="Connect")).to_have_count(0)
    page.locator(badge("connect")).click()
    expect(page.locator(circle("connect"))).to_have_count(1)
    expect(page.locator("#best .who strong")).to_have_text("Connect")
    expect(page.locator(ROWS)).to_have_count(5)


def test_with_a_gas_chosen_connects_stations_are_not_shown(page_at: Callable[[float, float], Page],
                                                           net: Net) -> None:
    page = open_five(page_at, net)
    page.get_by_text("თხევადი აირი", exact=True).first.click()
    expect(page.locator(circle("connect"))).to_have_count(0)
    page.get_by_text("ბუნებრივი აირი", exact=True).first.click()
    expect(page.locator(circle("connect"))).to_have_count(0)


def test_a_returning_visitor_finds_connect_on_and_keeps_its_own_choice(page_at: Callable[[float, float], Page],
                                                                       net: Net) -> None:
    page = open_five(page_at, net)
    page.evaluate("localStorage.setItem('fuel-map.off', JSON.stringify(['rompetrol', 'lukoil', 'wissol']))")
    page.reload()  # the visitor's list from before Connect was there
    expect(page.locator(f"{ROW} .badge")).to_have_count(len(FIVE))
    pressed = {cid: page.locator(badge(cid)).get_attribute("aria-pressed") for cid, *_ in FIVE}
    assert pressed == {"socar": "true", "rompetrol": "false", "lukoil": "false", "wissol": "false",
                       "connect": "true"}
    page.locator(badge("connect")).click()
    page.reload()
    expect(page.locator(badge("connect"))).to_have_attribute("aria-pressed", "false")
    assert sorted(json.loads(page.evaluate(STORED_OFF))) == ["connect", "lukoil", "rompetrol", "wissol"]
