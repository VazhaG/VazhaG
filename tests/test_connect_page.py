"""SPEC-0003 on the page — Connect as the fifth company (PLAN-0003 T4–T6).

T4: a company whose colour is light (its letters are dark: today Rompetrol and Connect) has a dark outline by day, on
its badge and on its map circles, so they stand out on the white page and the light map; at night the outline is as
before (REQ-003; AC-007).
"""

from __future__ import annotations

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
