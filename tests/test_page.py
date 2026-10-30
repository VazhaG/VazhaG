"""T1 — the page opens on a phone: a map with OpenStreetMap credit, the fuel choice, and no prices yet.

SPEC-0001: REQ-001, REQ-002, AC-001 (the part without prices and the ★ card).
"""

from __future__ import annotations

from html.parser import HTMLParser

from playwright.sync_api import Page, expect

from support import SITE, Net

FUELS = ["regular", "premium", "super", "diesel", "lpg", "cng"]  # REQ-002's order
FUELS_KA = ["რეგულარი", "პრემიუმი", "სუპერი", "დიზელი", "თხევადი აირი", "ბუნებრივი აირი"]


class Structure(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.lang: str | None = None
        self.charset: str | None = None
        self.viewport = False
        self.h1 = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "meta" and "charset" in a:
            self.charset = (a["charset"] or "").lower()
        elif tag == "meta" and a.get("name") == "viewport":
            self.viewport = True
        elif tag == "h1":
            self.h1 += 1


def test_index_structure() -> None:
    s = Structure()
    s.feed((SITE / "index.html").read_text(encoding="utf-8"))
    assert s.lang == "ka"
    assert s.charset == "utf-8"
    assert s.viewport
    assert s.h1 == 1


def test_phone_first_screen_without_prices(page: Page, net: Net) -> None:
    page.goto(net.base)
    expect(page.locator(".leaflet-container")).to_be_visible()
    expect(page.locator(".leaflet-control-attribution")).to_contain_text("OpenStreetMap")
    fuels = page.locator("input[name=fuel]")
    expect(fuels).to_have_count(len(FUELS))
    assert [fuels.nth(i).get_attribute("value") for i in range(len(FUELS))] == FUELS
    expect(page.locator(".chip span")).to_have_text(FUELS_KA)
    for name in FUELS_KA:
        expect(page.get_by_text(name, exact=True)).to_be_visible()
    expect(page.locator("#status")).to_contain_text("ფასები ჯერ არ არის")
    expect(page.locator("footer")).to_contain_text("ფასი სტანდარტულია")  # REQ-004
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert net.outside == []


def test_the_app_style_map_fills_the_screen_with_the_fuel_choice_on_it(page: Page, net: Net) -> None:
    # Layout 1 of intent §5 in the app style the owner chose (2026-10-30): the fuel choice floats on the map, the
    # map fills most of the first screen, and the sheet with the ★ card rises over its lower edge
    page.goto(net.base)
    expect(page.locator(".leaflet-control-zoom")).to_be_visible()
    view = page.viewport_size or {"height": 0}
    m, fuels, zoom, credit, sheet = (page.locator(s).bounding_box() or {} for s in (
        "#map", "#fuels", ".leaflet-control-zoom", ".leaflet-control-attribution", ".sheet"))
    assert m["height"] >= 0.55 * view["height"]
    assert m["y"] <= fuels["y"] and fuels["y"] + fuels["height"] <= m["y"] + m["height"]
    assert sheet["y"] < m["y"] + m["height"]
    assert fuels["y"] + fuels["height"] <= zoom["y"] and zoom["y"] + zoom["height"] <= sheet["y"]  # nothing covers it
    assert credit["y"] + credit["height"] <= sheet["y"]  # OpenStreetMap's credit stays in sight (its licence)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_the_chosen_fuel_is_shown_whole_in_its_row(page: Page, net: Net) -> None:
    # The six fuels do not fit a phone's width: the row scrolls sideways (never the page), and a fuel chosen at
    # its far end comes fully into view. Chosen here without Playwright's own scrolling.
    page.goto(net.base)
    page.evaluate("""() => { const input = document.querySelector('input[value=cng]');
                             input.checked = true; input.dispatchEvent(new Event('change', { bubbles: true })); }""")
    box = page.locator(".chip:has(input[value=cng])").bounding_box()
    width = (page.viewport_size or {"width": 0})["width"]
    assert box and box["x"] >= 0 and box["x"] + box["width"] <= width, box
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_at_night_the_page_follows_the_phones_dark_mode(page: Page, net: Net) -> None:
    # the owner's choice (2026-10-30); by day palette II of intent §5 stays
    background = "getComputedStyle(document.body).backgroundColor.match(/\\d+/g).slice(0, 3).map(Number)"
    page.emulate_media(color_scheme="dark")
    page.goto(net.base)
    assert max(page.evaluate(background)) < 64
    page.emulate_media(color_scheme="light")
    assert page.evaluate(background) == [255, 255, 255]  # palette II: white
