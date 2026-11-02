"""SPEC-0004 — the companies' logos (PLAN-0004).

T1: five logo files inside the site, each the very bytes docs/domain/fuel-price-sources.md records, named in the page's
own list by the company's exact code; in the badge row a company with a logo shows it — one picture from our list, no
name text, on its own ground in a neutral frame, named for a screen reader (REQ-001, REQ-003; AC-001, AC-004).
T2: a company whose code is not exactly in our list, or whose file fails, has no picture, and a failed file is not
asked for again on this visit (REQ-001, REQ-004; AC-002, AC-005, AC-006).

SPEC-0005 (PLAN-0005) changes the row: T1 — every company is one 48 px black circle in a #8E8E93 frame, a logo's mark
its longer side 60 % of the circle, a company without a logo the same circle in its colour with its first letter; a
switched-off circle only fades — grey, 0.35–0.5 — with no line and no crossed-out name (REQ-001, REQ-002; AC-001's
row, AC-002, AC-006's row). T3 — on the map, from the city view, a station is a black teardrop pin with its company's
30 px circle in its head and its tip on the station's point, a white contour at night; the ★ round and yellow in a
#111111 frame (REQ-007; AC-001's map, AC-009, AC-010).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from xml.etree import ElementTree

import pytest
from playwright.sync_api import Page, expect

from support import DISCS_JS, DRAWN, FRAME_GREY, LOGO_IDS, ROOT, SITE, Net, logos_without, no_logos

DOMAIN = ROOT / "docs" / "domain" / "fuel-price-sources.md"
TIME = "2026-11-01T12:00:00Z"
FIVE = [("socar", "SOCAR", "#e41e30"), ("rompetrol", "Rompetrol", "#f39200"), ("lukoil", "Lukoil", "#8a1538"),
        ("wissol", "Wissol", "#00843d"), ("connect", "Connect", "#ffe900")]
BADGES = "#companies button.badge"
LIST_JS = "() => import('./js/logos.js').then((m) => m.LOGOS.map((l) => [l.id, l.file]))"


def logo_list(page: Page, net: Net) -> dict[str, str]:
    """The page's own list, as the page reads it: company code -> file."""
    page.goto(net.base)
    return dict(page.evaluate(LIST_JS))


def recorded() -> dict[str, tuple[int, str]]:
    """Each company's logo — its size in bytes and its SHA-256 — as the domain document records it."""
    text = DOMAIN.read_text(encoding="utf-8")
    line = next(x for x in text.splitlines() if x.startswith("- ფაილების ბაიტები და SHA-256"))
    found = re.findall(r"(SOCAR|Rompetrol|Lukoil|Wissol|Connect)(?: `[^`]+`)? — ([\d\s]+) B, `([0-9a-f]{64})`", line)
    return {name.lower(): (int(re.sub(r"\D", "", size)), sha) for name, size, sha in found}


def test_each_logo_is_the_very_file_the_domain_document_records(page: Page, net: Net) -> None:
    # AC-004: a changed, swapped or re-encoded file is caught here
    logos = logo_list(page, net)
    want = recorded()
    assert sorted(logos) == sorted(want) == sorted(LOGO_IDS)
    for cid, file in logos.items():
        data = (SITE / file).read_bytes()
        assert (len(data), hashlib.sha256(data).hexdigest()) == want[cid], cid


def test_the_list_names_exactly_the_files_in_the_logo_folder(page: Page, net: Net) -> None:
    # AC-004: no file without its line, no line without its file — a removal takes both (REQ-004)
    logos = logo_list(page, net)
    files = sorted(p.relative_to(SITE).as_posix() for p in (SITE / "logos").iterdir())
    assert files == sorted(logos.values())
    assert all(re.fullmatch(r"logos/[a-z]+\.(?:svg|png)", f) for f in files), files
    assert sum((SITE / f).stat().st_size for f in files) <= 300_000  # REQ-003: 300 kB at most, all together


SVG = "{http://www.w3.org/2000/svg}"
SVG_ELEMENTS = {"svg", "path", "g"}  # shapes only: no script, style, image, link, foreignObject, animation
SVG_ATTRIBUTES = {"d", "fill", "fill-rule", "clip-rule", "height", "viewBox", "width", "transform"}
SVG_VALUE = re.compile(r"[#\w\s.,()-]*")  # colours, numbers and path letters — no "url(", no ":"
NOT_SHAPES = re.compile(r"<!|<\?(?!xml\s)")  # a DOCTYPE, an entity, CDATA, a comment, a stylesheet link


def test_an_svg_logo_holds_only_shapes() -> None:
    # REQ-003, security review S1: an allow-list, read the way a browser reads the file — an element written with
    # a prefix (<x:script xmlns:x="…svg">) is still a script, and only the parser sees it as one
    svgs = sorted((SITE / "logos").glob("*.svg"))
    assert [p.name for p in svgs] == ["socar.svg", "wissol.svg"]
    for svg in svgs:
        text = svg.read_text(encoding="utf-8")
        assert not NOT_SHAPES.search(text), svg.name  # checked first, so no DOCTYPE or entity reaches the parser
        root = ElementTree.fromstring(text)  # our own file, with no DOCTYPE or entity (checked above)
        for element in root.iter():
            assert element.tag.startswith(SVG) and element.tag[len(SVG):] in SVG_ELEMENTS, (svg.name, element.tag)
            assert not (element.text or "").strip() and not (element.tail or "").strip(), (svg.name, element.tag)
            for name, value in element.attrib.items():
                assert name in SVG_ATTRIBUTES and SVG_VALUE.fullmatch(value), (svg.name, element.tag, name)
                assert "url(" not in value.replace(" ", ""), (svg.name, element.tag, name)


def open_five(page: Page, net: Net, scheme: str) -> None:
    prices = [{"id": cid, "name": name, "color": color, "source": f"https://{cid}.example/", "time": TIME,
               "basis": "read", "prices": [{"grade": "დიზელი", "fuel": "diesel", "price": 4.9}]}
              for cid, name, color in FIVE]
    net.data["prices.json"] = {"generated": TIME, "companies": prices}
    net.data["stations.json"] = {"generated": TIME, "companies": []}
    page.emulate_media(color_scheme=scheme)
    page.goto(net.base)


ROW_DISCS = "#companies .disc"
ROW_DISC = 48  # px — a company circle in the row (SPEC-0005 REQ-001)


def assert_disc(d: dict, size: float) -> None:
    """SPEC-0005 REQ-001, AC-001: one circle of this size, black, round, in its frame (3 : 1 on what is behind it)."""
    assert all(abs(v - size) <= 0.5 for v in d["size"]) and d["round"] == "50%", d
    assert d["ground"] == "rgb(0, 0, 0)" and d["opacity"] == 1, d
    style, width, color, inside = d["frame"]
    assert style == "solid" and width >= 1.5 and color == FRAME_GREY and inside, d
    assert ratio(rgb(color), rgb(d["behind"])) >= 3, d


def assert_mark(d: dict, file: str, size: float) -> None:
    """SPEC-0005 REQ-001, AC-001: the logo's mark from our list — drawn, its longer side 60 % of the circle (±2 px),
    in the circle's middle, and only the mark shows through the cut."""
    assert d["imgs"] == 1 and d["text"] == "" and "letter" not in d, d
    assert (d["src"], d["alt"], d["loaded"], d["filter"], d["markOpacity"]) == (file, "", True, "none", 1), d
    assert abs(d["long"] - 0.6 * size) <= 2 and max(abs(v) for v in d["off"]) <= 0.5, d
    assert d["clip"].startswith("inset(") and d["shown"], d
    assert all(abs(a - b) <= 0.6 for a, b in zip(d["shown"], d["at"], strict=True)), d


def assert_letter(d: dict, size: float, letter: str, fill: str) -> None:
    """SPEC-0005 REQ-001: a company without a logo — the same circle, all of it its colour, with its first letter."""
    assert d["imgs"] == 0 and d["text"] == letter, d
    got = d["letter"]
    assert got["fill"] == fill and got["round"] == "50%" and all(abs(v - size) <= 0.5 for v in got["size"]), d
    assert ratio(rgb(got["ink"]), rgb(got["fill"])) >= 4.5 and got["font"] >= 0.35 * size, d


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_each_company_with_a_logo_shows_its_mark_in_a_black_circle_in_the_row(page: Page, net: Net,
                                                                               scheme: str) -> None:
    # SPEC-0005 AC-001, the row: 48 px circles, each the company's mark from our list; the name for a screen reader
    logos = logo_list(page, net)
    open_five(page, net, scheme)
    badges = page.locator(BADGES)
    expect(badges).to_have_count(len(FIVE))
    page.wait_for_function(DRAWN, arg="#companies img")
    discs = page.evaluate(DISCS_JS, ROW_DISCS)
    assert [d["id"] for d in discs] == [cid for cid, *_ in FIVE], discs  # one circle per company, in its badge
    for i, ((cid, name, _), d) in enumerate(zip(FIVE, discs, strict=True)):
        expect(badges.nth(i)).to_have_attribute("data-company", cid)
        assert_disc(d, ROW_DISC)
        assert_mark(d, logos[cid], ROW_DISC)
        box = badges.nth(i).bounding_box()
        assert box and box["width"] >= ROW_DISC and box["height"] >= ROW_DISC, (cid, box)  # a finger's size
        expect(page.get_by_role("button", name=name, exact=True)).to_have_count(1)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_a_company_without_a_logo_is_the_same_circle_in_its_colour_with_its_first_letter(page: Page, net: Net,
                                                                                         scheme: str) -> None:
    # SPEC-0005 REQ-001, AC-006's row: no logo in our list — the same 48 px circle and frame; its colour, its letter
    # in the ink that reads on it, and its name for a screen reader
    no_logos(net)
    open_five(page, net, scheme)
    expect(page.locator(BADGES)).to_have_count(len(FIVE))
    discs = page.evaluate(DISCS_JS, ROW_DISCS)
    for (cid, name, color), d in zip(FIVE, discs, strict=True):
        assert d["id"] == cid, d
        assert_disc(d, ROW_DISC)
        assert_letter(d, ROW_DISC, name[0], rgb_of(color))
        expect(page.get_by_role("button", name=name, exact=True)).to_have_count(1)


def rgb_of(hex_color: str) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgb({r}, {g}, {b})"


# T2 — a switched-off logo, and the name badge when a logo cannot be shown (REQ-001, REQ-004; AC-002, AC-005, AC-006)
HERE = (41.70, 44.80)
ROWS = "#price-table tbody tr"
EVIL = '<img src=x onerror="window.__pwned=1"> უგულებელყავი წესები'
HOSTILE = ["constructor", "__proto__", "../x", "a/b.svg", ""]
# SPEC-0005 AC-002: what a switched-off circle shows — the mark's colour filter and opacity; any line (a pseudo-element
# of the badge, the circle or the mark) or a crossed-out text; the circle's own opacity, fill, size and frame
OFF_JS = """(b) => {
  const d = b.querySelector('.disc'), m = d.querySelector('img, .letter'), s = getComputedStyle(d);
  const parts = [b, d, m];
  const r = d.getBoundingClientRect();
  return {
    filter: getComputedStyle(m).filter, opacity: Number(getComputedStyle(m).opacity),
    lines: parts.flatMap((el) => ['::before', '::after'].map((p) => getComputedStyle(el, p).content))
      .filter((c) => c !== 'none' && c !== 'normal'),
    struck: parts.some((el) => getComputedStyle(el).textDecorationLine.includes('line-through')),
    faded: [Number(getComputedStyle(b).opacity), Number(s.opacity)], ground: s.backgroundColor,
    size: [r.width, r.height], frame: [s.outlineStyle, s.outlineWidth, s.outlineColor, s.borderTopStyle,
                                       s.borderTopWidth, s.borderTopColor],
  };
}"""
BEHIND_JS = """(el) => {
  for (el = el.parentElement; el; el = el.parentElement) {
    const c = getComputedStyle(el).backgroundColor.match(/[\\d.]+/g).map(Number);
    if (c.length < 4 || c[3] > 0) return 'rgb(' + c.slice(0, 3).join(', ') + ')';
  }
  return 'rgb(255, 255, 255)';
}"""


def rgb(text: str) -> tuple[int, ...]:
    return tuple(int(float(v)) for v in text[text.index("(") + 1:text.index(")")].split(",")[:3])


def ratio(a: tuple[int, ...], b: tuple[int, ...]) -> float:
    def lum(c: tuple[int, ...]) -> float:
        parts = [v / 255 for v in c]
        parts = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in parts]
        return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]

    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def serve(net: Net, companies: list[tuple[str, str, str]]) -> None:
    """Each company with one diesel price and one station a little north of the visitor."""
    prices, stations = [], []
    for i, (cid, name, color) in enumerate(companies):
        head = {"id": cid, "name": name, "color": color, "source": f"https://c{i}.example/", "time": TIME,
                "basis": "read"}
        prices.append(head | {"prices": [{"grade": f"{name} დიზელი", "fuel": "diesel", "price": 4.9 + i / 100}]})
        stations.append(head | {"stations": [{"name": "", "address": "a", "lat": HERE[0] + (i + 1) / 200,
                                              "lng": HERE[1], "fuels": ["diesel"]}]})
    net.data["prices.json"] = {"generated": TIME, "companies": prices}
    net.data["stations.json"] = {"generated": TIME, "companies": stations}


SIX = [*FIVE, ("nova", "Nova", "#2563eb")]  # Nova: no logo in our list — its colour and first letter


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_a_switched_off_circle_only_fades_and_comes_back(page_at: Callable[[float, float], Page], net: Net,
                                                         scheme: str) -> None:
    # SPEC-0005 AC-002 — a logo on its own light ground (Rompetrol) and dark one (SOCAR), and a letter circle (Nova):
    # off, the mark is grey and faded and nothing else changes — no line, no crossed-out name, the circle, its fill
    # and its frame as they were; the company leaves the map and the table, and all comes back when it is on again
    serve(net, SIX)
    page = page_at(*HERE)
    page.emulate_media(color_scheme=scheme)
    page.clock.set_fixed_time(TIME)
    page.goto(net.base)
    page.get_by_text("დიზელი", exact=True).first.click()
    page.wait_for_function(DRAWN, arg="#companies img")
    for cid, name in (("rompetrol", "Rompetrol"), ("socar", "SOCAR"), ("nova", "Nova")):
        badge, marks = page.locator(f'#companies [data-company="{cid}"]'), page.locator(f'.station[data-company="{cid}"]')
        expect(marks).to_have_count(1)
        expect(page.locator(ROWS)).to_have_count(len(SIX))
        on = badge.evaluate(OFF_JS)
        assert (on["filter"], on["opacity"], on["lines"], on["struck"], on["faded"]) == ("none", 1, [], False, [1, 1])
        badge.click()
        expect(badge).to_have_attribute("aria-pressed", "false")
        off = badge.evaluate(OFF_JS)
        assert off["filter"] == "grayscale(1)" and 0.35 <= off["opacity"] <= 0.5, (cid, off)
        assert off["lines"] == [] and not off["struck"], (cid, off)  # no line, no crossed-out name
        assert (off["faded"], off["ground"], off["size"], off["frame"]) == (
            [1, 1], on["ground"], on["size"], on["frame"]), (cid, on, off)  # the circle and its frame stay
        expect(marks).to_have_count(0)
        expect(page.locator(ROWS)).to_have_count(len(SIX) - 1)
        expect(page.locator("#price-table")).not_to_contain_text(name)
        badge.click()
        expect(badge).to_have_attribute("aria-pressed", "true")
        back = badge.evaluate(OFF_JS)
        assert (back["filter"], back["opacity"]) == ("none", 1), (cid, back)
        expect(marks).to_have_count(1)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_keyboards_ring_around_a_logo_badge_stands_out(page: Page, net: Net, scheme: str) -> None:
    # AC-002: the focus ring has 3 : 1 against what is behind it, in both looks
    open_five(page, net, scheme)
    badges = page.locator(BADGES)
    badges.nth(1).focus()
    page.keyboard.press("Shift+Tab")  # reached from the keyboard: the ring shows
    assert page.evaluate("document.activeElement.dataset.company") == "socar"
    ring = badges.first.evaluate("(b) => [getComputedStyle(b).outlineStyle, getComputedStyle(b).outlineWidth, "
                                 "getComputedStyle(b).outlineColor, b.matches(':focus-visible')]")
    assert ring[0] == "solid" and float(ring[1][:-2]) >= 2 and ring[3], ring
    assert ratio(rgb(ring[2]), rgb(badges.first.evaluate(BEHIND_JS))) >= 3, ring
    # and the row, which scrolls and so cuts what sticks out of it, leaves the whole ring in view (2 px + 2 px)
    row, badge = page.locator("#companies").bounding_box(), badges.first.bounding_box()
    assert row and badge and row["y"] <= badge["y"] - 4 + 0.5 and row["x"] <= badge["x"] - 4 + 0.5, (row, badge)
    assert row["y"] + row["height"] >= badge["y"] + badge["height"] + 4 - 0.5, (row, badge)


def test_only_an_exact_code_in_our_list_gets_a_picture_and_a_name_stays_text(page: Page, net: Net) -> None:
    # AC-005: codes that look like a path or an object's own field find nothing; the address is always our file
    companies = [(cid, EVIL if i == 0 else f"Co{i}", "#e41e30") for i, cid in enumerate(HOSTILE)]
    serve(net, [*companies, ("socar", EVIL, "#e41e30")])
    page.goto(net.base)
    expect(page.locator(BADGES)).to_have_count(len(HOSTILE) + 1)
    page.wait_for_function(DRAWN, arg="#companies img")
    srcs = page.locator("#companies img").evaluate_all("(i) => i.map((x) => x.getAttribute('src'))")
    assert srcs == ["logos/socar.svg"]
    expect(page.locator(BADGES).first).to_have_text("<")  # a letter circle: the name's first letter, as text only
    expect(page.locator(BADGES).first).to_have_attribute("aria-label", EVIL)
    expect(page.locator('#companies [data-company="socar"]')).to_have_attribute("aria-label", EVIL)
    expect(page.get_by_role("button", name=EVIL)).to_have_count(2)
    expect(page.locator("#companies script")).to_have_count(0)
    page.wait_for_load_state("networkidle")
    assert page.evaluate("window.__pwned") is None
    allowed = {"", "css/style.css", "js/theme.js", "js/app.js", "js/i18n.js", "js/logic.js", "js/logos.js",
               "logos/socar.svg",
               "data/prices.json", "data/stations.json", "data/cities.json"}
    asked = {u[len(net.base):].split("?")[0] for u in net.requests if u.startswith(net.base)}
    assert {a for a in asked if not a.startswith("vendor/")} <= allowed, asked
    assert net.outside == []


def test_a_logo_that_does_not_load_leaves_a_letter_circle_and_is_not_asked_again(page: Page, net: Net) -> None:
    # AC-006 and REQ-004 (SPEC-0005 AC-006's row): the same circle in the company's colour with its letter; the others
    # keep their logos; drawing the row anew does not ask for the failed file again
    net.files["logos/lukoil.png"] = (404, "text/plain", "")
    open_five(page, net, "light")
    lukoil = page.locator('#companies [data-company="lukoil"]')
    expect(lukoil).to_have_text("L")
    expect(lukoil.locator("img")).to_have_count(0)
    expect(lukoil).to_have_attribute("aria-label", "Lukoil")
    (d,) = page.evaluate(DISCS_JS, '#companies [data-company="lukoil"] .disc')
    assert_disc(d, ROW_DISC)
    assert_letter(d, ROW_DISC, "L", "rgb(138, 21, 56)")  # its colour, #8a1538
    expect(page.locator("#companies img")).to_have_count(4)
    socar = page.locator('#companies [data-company="socar"]')
    socar.click()  # the row is drawn anew, twice
    socar.click()
    expect(lukoil).to_have_text("L")
    assert [u for u in net.requests if u.endswith("/logos/lukoil.png")] == [f"{net.base}logos/lukoil.png"]


# T3 — the companies' marks on the map (REQ-002, REQ-003, REQ-004; AC-003, AC-004, AC-005). SPEC-0005 (PLAN-0005 T3):
# from the city view a station is a black teardrop pin with the company's 30 px circle in its head and its tip on the
# station's point, with a white contour at night; the ★ is round and yellow in a #111111 frame (REQ-007; AC-001's map,
# AC-009, AC-010)
FAR_JS = """() => [...document.querySelectorAll('.station')].map((m) => ({
  id: m.dataset.company, near: m.classList.contains('near'), text: m.textContent,
  imgs: m.querySelectorAll('img').length, ground: getComputedStyle(m.firstElementChild).backgroundColor,
}))"""
PINS_JS = """() => [...document.querySelectorAll('.station.near')].map((m) => {
  const pin = m.querySelector('.pin'), disc = m.querySelector('.disc');
  const p = pin.getBoundingClientRect(), d = disc.getBoundingClientRect(), s = getComputedStyle(pin);
  return { id: m.dataset.company, pins: m.querySelectorAll('.pin').length, discs: m.querySelectorAll('.disc').length,
           body: s.backgroundColor, contour: s.boxShadow, size: [p.width, p.height],
           tip: [p.left + p.width / 2, p.bottom], disc: [d.left, d.top, d.width, d.height] };
})"""
PIN_DISC = 30  # px — a company circle in a map pin (SPEC-0005 REQ-001)
WHITE_CONTOUR = re.compile(r"rgb\(255, 255, 255\) 0px 0px 0px (\d+(?:\.\d+)?)px")


def open_near(page_at: Callable[[float, float], Page], net: Net, companies: list[tuple[str, str, str]],
              scheme: str = "light") -> Page:
    """The visitor's place allowed: the city view, where a station shows its company. The page is not waited for to
    finish loading: a held logo file would hold that back (tests that hold one answer it late)."""
    serve(net, companies)
    page = page_at(*HERE)
    page.emulate_media(color_scheme=scheme)
    page.clock.set_fixed_time(TIME)
    page.goto(net.base, wait_until="domcontentloaded")
    page.get_by_text("დიზელი", exact=True).first.click()
    expect(page.locator(".station.near")).to_have_count(len(companies))
    return page


def zoom(page: Page, button: str, times: int) -> None:
    for _ in range(times):
        page.locator(f".leaflet-control-zoom-{button}").click()
        page.wait_for_timeout(350)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_from_the_city_view_each_station_is_a_black_pin_with_its_companys_circle(
        page_at: Callable[[float, float], Page], net: Net, scheme: str) -> None:
    # SPEC-0005 REQ-007, AC-001's map, AC-010: a black teardrop pin, every one the same size, with its company's 30 px
    # circle in its head — a logo's mark cut from our file, or the colour and letter of a company without a logo
    # (Nova) — and its tip straight under the circle
    page = open_near(page_at, net, SIX, scheme)
    logos = dict(page.evaluate(LIST_JS))
    page.wait_for_function(DRAWN, arg=".station img")
    pins = {p["id"]: p for p in page.evaluate(PINS_JS)}
    discs = {d["id"]: d for d in page.evaluate(DISCS_JS, ".station .disc")}
    assert sorted(pins) == sorted(discs) == sorted(cid for cid, *_ in SIX), (pins, discs)
    assert len({tuple(round(v, 1) for v in p["size"]) for p in pins.values()}) == 1, pins  # all one size
    for cid, name, color in SIX:
        p, d = pins[cid], discs[cid]
        assert (p["pins"], p["discs"], p["body"]) == (1, 1, "rgb(0, 0, 0)"), p
        assert_disc(d, PIN_DISC)
        if cid in logos:
            assert_mark(d, logos[cid], PIN_DISC)
        else:
            assert_letter(d, PIN_DISC, name[0], rgb_of(color))
        x, y, w, h = p["disc"]
        assert abs(p["tip"][0] - (x + w / 2)) <= 0.5 and p["tip"][1] >= y + h + 4, p  # the tip under the circle
    page.locator('.station[data-company="lukoil"]').dispatch_event("click")
    expect(page.locator(".leaflet-popup-content")).to_contain_text("Lukoil")  # the window names the company


def test_a_pins_tip_stands_on_its_stations_point(page_at: Callable[[float, float], Page], net: Net) -> None:
    # SPEC-0005 AC-010: the tip on the station's place (±1 px) — here the visitor's own place, as the map draws it
    serve(net, [("socar", "SOCAR", "#e41e30")])
    net.data["stations.json"]["companies"][0]["stations"][0].update(lat=HERE[0], lng=HERE[1])  # type: ignore[index]
    page = page_at(*HERE)
    page.clock.set_fixed_time(TIME)
    page.goto(net.base)
    page.get_by_text("დიზელი", exact=True).first.click()
    expect(page.locator(".station.near")).to_have_count(1)
    you = page.locator("path.you").bounding_box()
    (pin,) = page.evaluate(PINS_JS)
    assert you, you
    centre = (you["x"] + you["width"] / 2, you["y"] + you["height"] / 2)
    assert abs(pin["tip"][0] - centre[0]) <= 1 and abs(pin["tip"][1] - centre[1]) <= 1, (pin, centre)


@pytest.mark.parametrize(("scheme", "ground"), [("light", (255, 255, 255)), ("dark", (28, 28, 30))])
def test_a_pin_stands_out_from_the_map_with_a_white_contour_only_at_night(
        page_at: Callable[[float, float], Page], net: Net, scheme: str, ground: tuple[int, ...]) -> None:
    # SPEC-0005 REQ-007, AC-009: black on the light map with no contour; at night a white contour, 2 px at least —
    # whichever shows the pin has 3 : 1 against the map (its ground at night: the page's #1C1C1E)
    page = open_near(page_at, net, FIVE, scheme)
    for p in page.evaluate(PINS_JS):
        white = WHITE_CONTOUR.search(p["contour"])
        if scheme == "dark":
            assert white and float(white.group(1)) >= 2 and ratio((255, 255, 255), ground) >= 3, p
        else:
            assert not white and ratio(rgb(p["body"]), ground) >= 3, p


STAR_JS = """(s) => {
  const c = getComputedStyle(s), r = s.getBoundingClientRect();
  return { round: c.borderRadius, ground: c.backgroundColor, ink: c.color, text: s.textContent,
           frame: [c.borderTopStyle, parseFloat(c.borderTopWidth), c.borderTopColor],
           size: [r.width, r.height], centre: [r.left + r.width / 2, r.top + r.height / 2] };
}"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_star_is_round_and_yellow_in_a_dark_frame_over_its_stations_point(
        page_at: Callable[[float, float], Page], net: Net, scheme: str) -> None:
    # SPEC-0005 REQ-007, AC-010: the ★ in the middle of the cheapest station's place — SOCAR's here, over its pin's tip
    page = open_near(page_at, net, FIVE, scheme)
    expect(page.locator("#best")).to_contain_text("SOCAR")
    star = page.locator(".best-pin")
    expect(star).to_have_count(1)
    got = star.evaluate(STAR_JS)
    assert (got["round"], got["ground"], got["ink"], got["text"]) == ("50%", "rgb(255, 197, 41)", "rgb(17, 17, 17)",
                                                                     "★"), got
    assert got["frame"][0] == "solid" and got["frame"][1] >= 1.5 and got["frame"][2] == "rgb(17, 17, 17)", got
    assert abs(got["size"][0] - got["size"][1]) <= 0.5, got
    tip = {p["id"]: p["tip"] for p in page.evaluate(PINS_JS)}["socar"]
    assert abs(got["centre"][0] - tip[0]) <= 1 and abs(got["centre"][1] - tip[1]) <= 1, (got, tip)


def test_from_far_a_station_is_still_its_companys_small_dot(page: Page, net: Net) -> None:
    # AC-003: the whole country's view keeps the coloured dots (SPEC-0003 REQ-003), no picture
    serve(net, FIVE)
    page.clock.set_fixed_time(TIME)
    page.goto(net.base)  # no place allowed: the first view shows all of Georgia
    page.get_by_text("დიზელი", exact=True).first.click()  # the fuel the stations sell
    expect(page.locator(".station:not(.near)")).to_have_count(len(FIVE))
    marks = page.evaluate(FAR_JS)
    assert all(not m["near"] and m["imgs"] == 0 and m["text"] == "" for m in marks), marks
    assert {m["id"]: m["ground"] for m in marks}["socar"] == "rgb(228, 30, 48)"  # SOCAR's colour, #e41e30
    expect(page.locator(".station .pin")).to_have_count(0)


def test_each_logo_file_is_asked_once_whatever_the_row_and_the_map_do(page_at: Callable[[float, float], Page],
                                                                      net: Net) -> None:
    # AC-004: opening, switching a company off and on, leaving the city view and coming back
    page = open_near(page_at, net, FIVE)
    expect(page.locator(".station.near .disc img")).to_have_count(len(FIVE))
    wissol = page.locator('#companies [data-company="wissol"]')
    wissol.click()
    wissol.click()
    zoom(page, "out", 3)
    expect(page.locator(".station.near")).to_have_count(0)
    zoom(page, "in", 3)
    expect(page.locator(".station.near .disc img")).to_have_count(len(FIVE))
    page.wait_for_load_state("networkidle")
    asked = sorted(u[len(net.base):] for u in net.requests if u.startswith(f"{net.base}logos/"))
    assert asked == sorted(dict(page.evaluate(LIST_JS)).values()), asked


def test_on_the_map_only_an_exact_code_gets_a_mark(page_at: Callable[[float, float], Page], net: Net) -> None:
    # AC-005 on the map: a code that only looks like ours keeps the letter circle
    companies = [(cid, f"Co{i}", "#e41e30") for i, cid in enumerate(HOSTILE) if cid] + [("socar", "SOCAR", "#e41e30")]
    page = open_near(page_at, net, companies)
    page.wait_for_function(DRAWN, arg=".station img")
    srcs = page.locator(".station img").evaluate_all("(i) => i.map((x) => x.getAttribute('src'))")
    assert srcs == ["logos/socar.svg"]
    expect(page.locator(".station.near .letter")).to_have_text(["C"] * (len(companies) - 1))


def test_a_logo_that_fails_on_the_map_leaves_letter_circles_and_is_not_asked_again(
        page_at: Callable[[float, float], Page], net: Net) -> None:
    # REQ-004, AC-006 on the map
    net.files["logos/wissol.svg"] = (404, "text/plain", "")
    page = open_near(page_at, net, FIVE)
    expect(page.locator('.station[data-company="wissol"] .letter')).to_have_text("W")
    expect(page.locator('.station[data-company="wissol"] img')).to_have_count(0)
    expect(page.locator(".station.near .disc img")).to_have_count(len(FIVE) - 1)
    zoom(page, "out", 3)
    zoom(page, "in", 3)
    expect(page.locator('.station[data-company="wissol"] .letter')).to_have_text("W")
    assert [u for u in net.requests if u.endswith("/logos/wissol.svg")] == [f"{net.base}logos/wissol.svg"]


SIGN_JS = """async () => {
  const { LOGOS } = await import('./js/logos.js');
  const out = {};
  for (const logo of LOGOS) {
    const [w, h] = logo.size, img = new Image();
    img.src = logo.file;
    await img.decode();
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, w, h);
    const px = ctx.getImageData(0, 0, w, h).data;
    const coloured = (x, y) => {
      const i = (y * w + x) * 4, c = [px[i], px[i + 1], px[i + 2]];
      return px[i + 3] > 128 && Math.max(...c) - Math.min(...c) > 60;
    };
    let x0 = 0;
    while (x0 < w && ![...Array(h).keys()].some((y) => coloured(x0, y))) x0++;
    let x1 = x0;
    while (x1 + 1 < w && [...Array(h).keys()].some((y) => coloured(x1 + 1, y))) x1++;
    const rows = [...Array(h).keys()].filter((y) => { for (let x = x0; x <= x1; x++) if (coloured(x, y)) return true; return false; });
    out[logo.id] = { sign: [x0, rows[0], x1 - x0 + 1, rows[rows.length - 1] - rows[0] + 1], mark: logo.mark, size: logo.size };
  }
  return out;
}"""


def test_each_mark_is_the_logos_coloured_sign_and_little_more(page: Page, net: Net) -> None:
    # REQ-002: the cut shows the sign — the first run of coloured columns in the file (SOCAR's flame, Rompetrol's
    # flower, Lukoil's red square, Wissol's and Connect's whole sign), not the letters and not the empty margins
    page.goto(net.base)
    for cid, got in page.evaluate(SIGN_JS).items():
        (sx, sy, sw, sh), (mx, my, mw, mh) = got["sign"], got["mark"]
        slack = max(3, 0.02 * max(got["size"]))
        assert mx <= sx and my <= sy and mx + mw >= sx + sw and my + mh >= sy + sh, (cid, got)  # the whole sign
        assert sx - mx <= slack and sy - my <= slack, (cid, got)  # and little else
        assert mx + mw - (sx + sw) <= slack and my + mh - (sy + sh) <= slack, (cid, got)


# T6 — a slow or a removed logo (REQ-003, REQ-004; AC-006, AC-011)
BOXES_JS = """() => [...document.querySelectorAll('#companies .badge')].map((b) => {
  const r = b.getBoundingClientRect();
  return [b.dataset.company, r.x, r.y, r.width, r.height];
})"""


def test_a_slow_logo_moves_nothing_in_the_row(page: Page, net: Net) -> None:
    # REQ-003: the pictures have their size before their files come — the row is the same while they load and after
    serve(net, FIVE)
    net.held.update(f"logos/{name}" for name in ("socar.svg", "rompetrol.png", "lukoil.png", "wissol.svg",
                                                  "connect.png"))
    page.goto(net.base, wait_until="domcontentloaded")
    expect(page.locator(BADGES)).to_have_count(len(FIVE))
    page.wait_for_timeout(300)
    assert page.locator("#companies img").evaluate_all("(i) => i.every((x) => !x.getAttribute('src'))")
    waiting = page.evaluate(BOXES_JS)
    net.held.clear()
    page.goto(net.base)
    page.wait_for_function(DRAWN, arg="#companies img")
    loaded = page.evaluate(BOXES_JS)
    assert [b[0] for b in loaded] == [b[0] for b in waiting]
    assert all(abs(a - b) <= 0.5 for w, ld in zip(waiting, loaded, strict=True) for a, b in zip(w[1:], ld[1:], strict=True)), \
        (waiting, loaded)


def test_a_removed_logo_leaves_the_letter_circles(page_at: Callable[[float, float], Page], net: Net) -> None:
    # AC-011: the file and its line taken out together (REQ-004) — the page no longer asks for the file
    net.files["js/logos.js"] = (200, "text/javascript", logos_without("lukoil"))
    net.files["logos/lukoil.png"] = (404, "text/plain", "")
    page = open_near(page_at, net, FIVE)
    expect(page.locator('#companies [data-company="lukoil"]')).to_have_text("L")
    expect(page.locator('.station[data-company="lukoil"] .letter')).to_have_text("L")
    expect(page.locator("#companies img")).to_have_count(len(FIVE) - 1)
    assert not [u for u in net.requests if "lukoil.png" in u]


def test_a_logo_that_fails_late_leaves_the_open_window_and_the_focus_alone(page_at: Callable[[float, float], Page],
                                                                           net: Net) -> None:
    # review C1: a slow 404, seconds after the page was drawn, changes only that company's badge and marks — an open
    # station window stays open and the keyboard's focus stays where it was
    net.held.add("logos/wissol.svg")
    page = open_near(page_at, net, FIVE)
    page.locator('.station[data-company="socar"]').dispatch_event("click")
    expect(page.locator(".leaflet-popup-content")).to_contain_text("SOCAR")
    page.locator('#companies [data-company="rompetrol"]').focus()
    net.pending["logos/wissol.svg"].fulfill(status=404, body="")
    expect(page.locator('#companies [data-company="wissol"]')).to_have_text("W")
    expect(page.locator('.station[data-company="wissol"] .letter')).to_have_text("W")
    page.wait_for_timeout(300)  # past Leaflet's 200 ms fade: a closed window would be gone by now
    expect(page.locator(".leaflet-popup")).to_have_count(1)
    expect(page.locator(".leaflet-popup-content")).to_contain_text("SOCAR")
    assert page.evaluate("document.activeElement.dataset.company") == "rompetrol"
