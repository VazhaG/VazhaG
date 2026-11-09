"""SPEC-0006 — the iOS "Liquid Glass" controls and the light look's colours (PLAN-0006 T1).

T1: on the map's top and in the header, the two filter buttons, the fuel chips that are not chosen, the open filter
panel, the map's + / − and the look and language switches are glass — white 0.55 by day, #1C1C1E 0.65 at night, what is
under them blurred 24 px and its colours made stronger (`blur(24px) saturate(180%)`), a 1 px light edge, a light line
along the top edge and a soft shadow; capsule shapes. Only full-strength text sits on the glass (#0F172A by day, white
at night), so every text has 4.5 : 1 on the glass whatever is under it: the glass is drawn on black and on white, the
two ends of every colour. The chosen fuel and language stay solid yellow. A browser that cannot blur, and a visitor who
asks for less transparency, get the solid surface instead (REQ-001, REQ-002, REQ-003; AC-001, AC-002, AC-003).
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest
from playwright.sync_api import Page, expect

from support import SITE, Net, ratio, rgb

TIME = "2026-11-02T12:00:00Z"
HERE = (41.70, 44.80)
FIVE = [("socar", "SOCAR", "#e41e30"), ("rompetrol", "Rompetrol", "#f39200"), ("lukoil", "Lukoil", "#8a1538"),
        ("wissol", "Wissol", "#00843d"), ("connect", "Connect", "#ffe900")]
CSS_FILE = SITE / "css" / "style.css"
# the condition the glass stands behind: a browser that can blur, by either name (REQ-002)
GLASS_GATE = "@supports (backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))"
# every glass control, by what it is: (selector, the shape's corner radius)
GLASS = [(".filter-button", "26px"), (".chip input:not(:checked) + span", "999px"), ("#panel-company", "26px"),
         (".leaflet-control-zoom-in", "50%"), (".leaflet-control-zoom-out", "50%"), ("#theme", "50%"),
         (".lang", "999px")]
LOOK = {
    "light": {"glass": "rgba(255, 255, 255, 0.55)", "edge": "rgba(255, 255, 255, 0.65)", "ink": "rgb(15, 23, 42)",
              "solid": "rgb(255, 255, 255)"},
    "dark": {"glass": "rgba(28, 28, 30, 0.65)", "edge": "rgba(255, 255, 255, 0.16)", "ink": "rgb(255, 255, 255)",
             "solid": "rgb(44, 44, 46)"},
}
BLUR = "blur(24px) saturate(1.8)"  # how the browser writes blur(24px) saturate(180%)
GLASS_JS = """(sel) => [...document.querySelectorAll(sel)].map((el) => {
  const s = getComputedStyle(el), r = el.getBoundingClientRect();
  return { ground: s.backgroundColor, blur: s.backdropFilter, edge: [s.borderTopStyle, s.borderTopWidth, s.borderTopColor],
           shadow: s.boxShadow, radius: s.borderTopLeftRadius, size: [r.width, r.height] };
})"""
# every text that sits on the glass, with the glass it sits on: its colour, the glass's colour, and its weight
TEXTS = [(".filter-name", ".filter-button"), (".filter-value", ".filter-button"), (".chip input:not(:checked) + span",
         ".chip input:not(:checked) + span"), ("#panel-company .option-name", "#panel-company"),
         (".leaflet-control-zoom-in", ".leaflet-control-zoom-in"), (".leaflet-control-zoom-out", ".leaflet-control-zoom-out"),
         ("#theme", "#theme"), ('.lang button[aria-pressed="false"]', ".lang")]
TEXT_JS = """([sel, under]) => [...document.querySelectorAll(sel)].map((el) => {
  const glass = el.matches(under) ? el : el.closest(under) || document.querySelector(under);
  const s = getComputedStyle(el);
  return { text: (el.textContent || '').trim().slice(0, 20), ink: s.color, weight: Number(s.fontWeight),
           glass: getComputedStyle(glass).backgroundColor, arrow: getComputedStyle(el, '::after').color };
})"""


def serve(net: Net) -> None:
    prices, stations = [], []
    for i, (cid, name, color) in enumerate(FIVE):
        head = {"id": cid, "name": name, "color": color, "source": f"https://c{i}.example/", "time": TIME,
                "basis": "read"}
        prices.append(head | {"prices": [{"grade": f"{name} დიზელი", "fuel": "diesel", "price": 4.9 + i / 100},
                                         {"grade": f"{name} რეგულარი", "fuel": "regular", "price": 3.9 + i / 100}]})
        stations.append(head | {"stations": [{"name": "", "address": "a", "lat": HERE[0] + (i + 1) / 300,
                                              "lng": HERE[1], "fuels": ["regular", "diesel"]}]})
    net.data["prices.json"] = {"generated": TIME, "companies": prices}
    net.data["stations.json"] = {"generated": TIME, "companies": stations}


def open_page(page_at: Callable[[float, float], Page], net: Net, scheme: str) -> Page:
    serve(net)
    page = page_at(*HERE)
    page.emulate_media(color_scheme=scheme)
    page.clock.set_fixed_time(TIME)
    page.goto(net.base)
    expect(page.locator("#best a.go-google")).to_be_visible()
    page.locator("#filter-company").click()  # the open panel is glass too
    expect(page.locator("#panel-company")).to_be_visible()
    return page


def rgba(text: str) -> tuple[tuple[int, ...], float]:
    """'rgba(1, 2, 3, 0.5)' or 'rgb(1, 2, 3)' -> ((1, 2, 3), alpha)."""
    v = [float(x) for x in text[text.index("(") + 1:text.index(")")].split(",")]
    return tuple(round(x) for x in v[:3]), (v[3] if len(v) > 3 else 1.0)


def on(glass: str, ground: tuple[int, ...]) -> tuple[int, ...]:
    """The glass drawn on one colour: each channel alpha × glass + (1 − alpha) × what is under it."""
    colour, alpha = rgba(glass)
    return tuple(round(alpha * c + (1 - alpha) * g) for c, g in zip(colour, ground, strict=True))


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_controls_on_the_map_and_in_the_header_are_glass(page_at: Callable[[float, float], Page], net: Net,
                                                             scheme: str) -> None:
    # AC-001: each glass control has the look's glass colour and opacity, the blur, a 1 px light edge, a light line along
    # its top edge with a soft shadow under it, and its capsule shape; the + / − are 40 px circles
    page = open_page(page_at, net, scheme)
    look = LOOK[scheme]
    for selector, radius in GLASS:
        found = page.evaluate(GLASS_JS, selector)
        assert found, selector
        for g in found:
            assert (g["ground"], g["blur"], g["radius"]) == (look["glass"], BLUR, radius), (selector, g)
            assert g["edge"] == ["solid", "1px", look["edge"]], (selector, g)
            assert "inset" in g["shadow"] and g["shadow"].count("px") >= 8, (selector, g)  # the line and the shadow
            if "zoom" in selector:
                assert all(abs(v - 40) <= 0.5 for v in g["size"]), (selector, g)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_every_text_on_the_glass_reads_whatever_is_under_it(page_at: Callable[[float, float], Page], net: Net,
                                                           scheme: str) -> None:
    # AC-002: each text on the glass is the look's full-strength ink (the filter's small name too, in bold), and has
    # 4.5 : 1 on its glass drawn on black and on white — every colour under the glass lies between the two
    page = open_page(page_at, net, scheme)
    ink = LOOK[scheme]["ink"]
    checked = 0
    for selector, under in TEXTS:
        for t in page.evaluate(TEXT_JS, [selector, under]):
            assert t["ink"] == ink, (selector, t)
            for ground in ((0, 0, 0), (255, 255, 255)):
                assert ratio(rgb(t["ink"]), on(t["glass"], ground)) >= 4.5, (selector, ground, t)
            checked += 1
    arrows = page.evaluate(TEXT_JS, [".filter-button", ".filter-button"])
    assert {a["arrow"] for a in arrows} == {ink}, arrows  # the ▾ is drawn in the same ink
    names = page.evaluate(TEXT_JS, [".filter-name", ".filter-button"])
    assert all(n["weight"] >= 600 for n in names), names  # small and bold, not grey
    assert checked >= 15, checked


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_chosen_fuel_and_language_stay_solid_yellow(page_at: Callable[[float, float], Page], net: Net,
                                                        scheme: str) -> None:
    # AC-001: the chosen ones are not glass — solid #FFC529 with #111111 bold letters
    page = open_page(page_at, net, scheme)
    for sel in (".chip input:checked + span", '.lang button[aria-pressed="true"]'):
        got = page.locator(sel).evaluate(
            "(el) => { const s = getComputedStyle(el); return [s.backgroundColor, s.color, Number(s.fontWeight)]; }")
        assert got[:2] == ["rgb(255, 197, 41)", "rgb(17, 17, 17)"] and got[2] >= 700, (sel, got)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_a_browser_that_cannot_blur_shows_the_solid_surface(page_at: Callable[[float, float], Page], net: Net,
                                                            scheme: str) -> None:
    # AC-003: the glass stands behind one condition — a browser that can blur, by either name; a browser that cannot
    # skips it, as here, where the condition asks for a property no browser has: every control is the solid surface
    text = CSS_FILE.read_text(encoding="utf-8")
    assert text.count(GLASS_GATE) == 1, "the glass stands behind exactly one blur condition"
    net.files["css/style.css"] = (200, "text/css", text.replace(GLASS_GATE, "@supports (no-such-property: none)"))
    page = open_page(page_at, net, scheme)
    solid = LOOK[scheme]["solid"]
    for selector, _ in GLASS:
        for g in page.evaluate(GLASS_JS, selector):
            assert (g["ground"], g["blur"]) == (solid, "none"), (selector, g)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_a_visitor_who_asks_for_less_transparency_gets_the_solid_surface(page_at: Callable[[float, float], Page],
                                                                       net: Net, scheme: str) -> None:
    # AC-003: the phone's "reduce transparency" (prefers-reduced-transparency), set here as the browser's own emulation
    page = open_page(page_at, net, scheme)
    cdp = page.context.new_cdp_session(page)
    cdp.send("Emulation.setEmulatedMedia",
             {"features": [{"name": "prefers-reduced-transparency", "value": "reduce"},
                           {"name": "prefers-color-scheme", "value": scheme}]})
    page.wait_for_function("() => matchMedia('(prefers-reduced-transparency: reduce)').matches")
    solid = LOOK[scheme]["solid"]
    for selector, _ in GLASS:
        for g in page.evaluate(GLASS_JS, selector):
            assert (g["ground"], g["blur"]) == (solid, "none"), (selector, g)


def test_the_glass_names_the_blur_both_ways_in_the_stylesheet() -> None:
    # REQ-001: Safari on older iPhones knows the blur only as -webkit-backdrop-filter; the browser in these tests drops
    # that name, so the stylesheet itself is read: inside the glass condition every blur is written both ways, alike
    text = CSS_FILE.read_text(encoding="utf-8")
    block = text[text.index(GLASS_GATE) + len(GLASS_GATE):]  # the rules after the condition, not the condition
    plain = re.findall(r"(?<![-\w])backdrop-filter:\s*([^;]+);", block)
    webkit = re.findall(r"-webkit-backdrop-filter:\s*([^;]+);", block)
    assert plain and plain == webkit, (plain, webkit)
