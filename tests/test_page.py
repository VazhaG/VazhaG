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
