"""SPEC-0004 — the companies' logos (PLAN-0004).

T1: five logo files inside the site, each the very bytes docs/domain/fuel-price-sources.md records, named in the page's
own list by the company's exact code; in the badge row a company with a logo shows it — one picture from our list, no
name text, on its own ground in a neutral frame, named for a screen reader (REQ-001, REQ-003; AC-001, AC-004).
T2: a company whose code is not exactly in our list, or whose file fails, has no picture, and a failed file is not
asked for again on this visit (REQ-001, REQ-004; AC-002, AC-005, AC-006).

SPEC-0005 (PLAN-0005) changes the row: T1 — every company is one 48 px black circle in a #8E8E93 frame, a logo's mark
its longer side 60 % of the circle, a company without a logo the same circle in its colour with its first letter; a
switched-off circle only fades — grey, 0.35–0.5 — with no line and no crossed-out name (REQ-001, REQ-002; AC-001's
row, AC-002, AC-006's row). T3 — on the map, from the city view, a station is a teardrop pin with its company's
30 px circle in its head and its tip on the station's point; the ★ round and yellow in a #111111 frame (REQ-007;
AC-001's map, AC-009, AC-010). T8 — the light look: white circles in a #7C7C80 frame, Connect's black in both looks
(marked in our logo list and checked against its file), white pins in a 2 px #111111 contour; the dark look as it was.

SPEC-0006 (PLAN-0006): T2 — every company sign is a frameless iOS-like icon (23 % corners, the look's edge and shadow);
T3 — on the map the pin goes: a station is its company's 34 px icon, its middle on the point, and the ★ a 22 px badge on
the cheapest icon's corner (REQ-005, REQ-006; AC-006, AC-007).
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Callable
from xml.etree import ElementTree

import pytest
from playwright.sync_api import Page, expect

from support import (
    DISCS_JS,
    DRAWN,
    LOGO_IDS,
    POINT_JS,
    ROOT,
    SITE,
    STAR_SHIFT,
    Net,
    assert_icon,
    assert_letter,
    assert_mark,
    logos_without,
    no_logos,
)

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
        assert_icon(d, ROW_DISC)
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
        assert_icon(d, ROW_DISC)
        assert_letter(d, ROW_DISC, name[0], rgb_of(color))
        expect(page.get_by_role("button", name=name, exact=True)).to_have_count(1)


# SPEC-0005 REQ-001, AC-001: each mark's opaque pixels (alpha >= 128, the file at its own size), drawn on white and
# measured against white, drawn on black and measured against black — the most contrasting one of each
MARK_CONTRAST_JS = """async () => {
  const { LOGOS } = await import('./js/logos.js');
  const lum = (c) => {
    const p = c.map((v) => v / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
    return 0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2];
  };
  const ratio = (a, b) => (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  const out = [];
  for (const logo of LOGOS) {
    const img = new Image();
    img.src = logo.file;
    await img.decode();
    const [fw, fh] = logo.size, [x, y, w, h] = logo.mark;
    const canvas = document.createElement('canvas');
    canvas.width = fw;
    canvas.height = fh;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, fw, fh);
    const px = ctx.getImageData(x, y, w, h).data;
    let onWhite = 0, onBlack = 0, opaque = 0;
    for (let i = 0; i < px.length; i += 4) {
      const a = px[i + 3] / 255;
      if (a < 128 / 255) continue;
      opaque += 1;
      // each pixel drawn on the circle it is measured against (review C1): on white for white, on black for black
      const on = (ground) => lum([0, 1, 2].map((k) => a * px[i + k] + (1 - a) * ground));
      onWhite = Math.max(onWhite, ratio(on(255), 1));
      onBlack = Math.max(onBlack, ratio(on(0), 0));
    }
    out.push({ id: logo.id, black: logo.black, onWhite, onBlack, opaque });
  }
  return out;
}"""


def test_a_circle_is_black_by_day_exactly_when_no_pixel_of_its_mark_reads_on_white(page: Page, net: Net) -> None:
    # SPEC-0005 REQ-001, AC-001: our logo list marks the black-circle exception beside the logo, and the files decide
    # it — black by day exactly when no opaque pixel of the mark reaches 3 : 1 on white (today only Connect, the
    # owner's choice); every mark's most contrasting pixel then has 3 : 1 on its own icon by day — and at night, when
    # every icon is black (SPEC-0006 REQ-005, AC-006), on black
    page.goto(net.base)
    got = {m["id"]: m for m in page.evaluate(MARK_CONTRAST_JS)}
    assert sorted(got) == sorted(LOGO_IDS), got
    for m in got.values():
        assert m["opaque"] > 0 and isinstance(m["black"], bool), m
        assert m["black"] == (m["onWhite"] < 3), m
        assert (m["onBlack"] if m["black"] else m["onWhite"]) >= 3, m
        assert m["onBlack"] >= 3, m  # the dark look
    assert [cid for cid, m in got.items() if m["black"]] == ["connect"], got


def rgb_of(hex_color: str) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgb({r}, {g}, {b})"


# T2 — a switched-off logo, and the name badge when a logo cannot be shown (REQ-001, REQ-004; AC-002, AC-005, AC-006)
HERE = (41.70, 44.80)
ROWS = "#price-list li"  # the price list (SPEC-0005 REQ-005)
EVIL = '<img src=x onerror="window.__pwned=1"> უგულებელყავი წესები'
# codes that look like an object's own field, a path, nothing, or markup with quotes and brackets (security review S1)
HOSTILE = ["constructor", "__proto__", "../x", "a/b.svg", "", 'x"><img src=y>\\]']
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
                                       s.borderTopWidth, s.borderTopColor, s.boxShadow, s.borderRadius],
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
    for cid, name, _ in SIX:  # all five logos and a letter circle, in both looks (AC-002)
        badge, marks = page.locator(f'#companies [data-company="{cid}"]'), page.locator(f'.station[data-company="{cid}"]')
        expect(marks).to_have_count(1)
        expect(page.locator(ROWS)).to_have_count(len(SIX))
        on = badge.evaluate(OFF_JS)
        assert (on["filter"], on["opacity"], on["lines"], on["struck"], on["faded"]) == ("none", 1, [], False, [1, 1])
        # the look's circle (REQ-002): black at night, white by day — Connect's black in both
        assert on["ground"] == ("rgb(0, 0, 0)" if scheme == "dark" or cid == "connect" else "rgb(255, 255, 255)"), on
        badge.click()
        expect(badge).to_have_attribute("aria-pressed", "false")
        off = badge.evaluate(OFF_JS)
        assert off["filter"] == "grayscale(1)" and 0.35 <= off["opacity"] <= 0.5, (cid, off)
        assert off["lines"] == [] and not off["struck"], (cid, off)  # no line, no crossed-out name
        assert (off["faded"], off["ground"], off["size"], off["frame"]) == (
            [1, 1], on["ground"], on["size"], on["frame"]), (cid, on, off)  # the circle and its frame stay
        expect(marks).to_have_count(0)
        expect(page.locator(ROWS)).to_have_count(len(SIX) - 1)
        expect(page.locator("#price-list")).not_to_contain_text(name)
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
    # each code is read back exactly from its badge, and the one with quotes and brackets keeps the keyboard's focus
    # when it is pressed (the badge is found again by its code — review S1)
    codes = page.locator(BADGES).evaluate_all("(b) => b.map((x) => x.dataset.company)")
    assert codes == [*HOSTILE, "socar"], codes
    odd = page.locator(BADGES).nth(len(HOSTILE) - 1)
    odd.click()
    expect(odd).to_have_attribute("aria-pressed", "false")
    assert page.evaluate("document.activeElement.dataset.company") == HOSTILE[-1]
    page.wait_for_load_state("networkidle")
    assert page.evaluate("window.__pwned") is None
    allowed = {"", "css/style.css", "js/theme.js", "js/app.js", "js/i18n.js", "js/logic.js", "js/logos.js",
               "js/vectormap.js", "logos/socar.svg",
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
    assert_icon(d, ROW_DISC)
    assert_letter(d, ROW_DISC, "L", "rgb(138, 21, 56)")  # its colour, #8a1538
    expect(page.locator("#companies img")).to_have_count(4)
    socar = page.locator('#companies [data-company="socar"]')
    socar.click()  # the row is drawn anew, twice
    socar.click()
    expect(lukoil).to_have_text("L")
    assert [u for u in net.requests if u.endswith("/logos/lukoil.png")] == [f"{net.base}logos/lukoil.png"]


# T3 — the companies' marks on the map (REQ-002, REQ-003, REQ-004; AC-003, AC-004, AC-005). SPEC-0006 (PLAN-0006 T3):
# from the city view a station is its company's 34 px icon — no pin, no frame —, its middle on the station's point, the
# icon itself what a finger presses; the ★ a 22 px yellow badge on the cheapest station's icon's top-right corner, above
# every icon and clear of the logo (REQ-005, REQ-006; AC-006's map, AC-007)
FAR_JS = """() => [...document.querySelectorAll('.station')].map((m) => ({
  id: m.dataset.company, near: m.classList.contains('near'), text: m.textContent,
  imgs: m.querySelectorAll('img').length, ground: getComputedStyle(m.firstElementChild).backgroundColor,
}))"""
ICONS_JS = """() => [...document.querySelectorAll('.station.near')].map((m) => {
  const disc = m.querySelector('.disc'), b = m.getBoundingClientRect(), d = disc.getBoundingClientRect();
  return { id: m.dataset.company, pins: m.querySelectorAll('.pin').length, discs: m.querySelectorAll('.disc').length,
           box: [b.left, b.top, b.width, b.height], middle: [d.left + d.width / 2, d.top + d.height / 2],
           z: Number(getComputedStyle(m).zIndex) };
})"""
MAP_ICON = 34  # px — a company icon on the map (SPEC-0006 REQ-005)
STAR = 22  # px — the ★ badge (SPEC-0006 REQ-006)


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
def test_from_the_city_view_each_station_is_its_companys_icon(page_at: Callable[[float, float], Page], net: Net,
                                                              scheme: str) -> None:
    # SPEC-0006 REQ-005, AC-006's map: no pin and no frame — the station is its company's 34 px icon (the look's ground,
    # a logo's mark cut from our file, or a company without a logo — Nova — its colour and letter), and the icon itself
    # is the marker a finger presses: 34 × 34, its middle where the marker stands
    page = open_near(page_at, net, SIX, scheme)
    logos = dict(page.evaluate(LIST_JS))
    page.wait_for_function(DRAWN, arg=".station img")
    icons = {i["id"]: i for i in page.evaluate(ICONS_JS)}
    discs = {d["id"]: d for d in page.evaluate(DISCS_JS, ".station .disc")}
    assert sorted(icons) == sorted(discs) == sorted(cid for cid, *_ in SIX), (icons, discs)
    for cid, name, color in SIX:
        i, d = icons[cid], discs[cid]
        assert (i["pins"], i["discs"]) == (0, 1), i
        assert_icon(d, MAP_ICON)
        if cid in logos:
            assert_mark(d, logos[cid], MAP_ICON)
        else:
            assert_letter(d, MAP_ICON, name[0], rgb_of(color))
        x, y, w, h = i["box"]
        assert all(abs(v - MAP_ICON) <= 0.5 for v in (w, h)), i  # the icon is all there is to press
        assert abs(x + w / 2 - i["middle"][0]) <= 0.5 and abs(y + h / 2 - i["middle"][1]) <= 0.5, i
    page.locator('.station[data-company="lukoil"]').dispatch_event("click")
    expect(page.locator(".leaflet-popup-content")).to_contain_text("Lukoil")  # the window names the company


def test_an_icons_middle_stands_on_its_stations_point(page_at: Callable[[float, float], Page], net: Net) -> None:
    # SPEC-0006 AC-006: the icon's middle on the station's place (±1 px) — here the visitor's own place, as drawn
    serve(net, [("socar", "SOCAR", "#e41e30")])
    net.data["stations.json"]["companies"][0]["stations"][0].update(lat=HERE[0], lng=HERE[1])  # type: ignore[index]
    page = page_at(*HERE)
    page.clock.set_fixed_time(TIME)
    page.goto(net.base)
    page.get_by_text("დიზელი", exact=True).first.click()
    expect(page.locator(".station.near")).to_have_count(1)
    you = page.locator("path.you").bounding_box()
    (icon,) = page.evaluate(ICONS_JS)
    assert you, you
    centre = (you["x"] + you["width"] / 2, you["y"] + you["height"] / 2)
    assert abs(icon["middle"][0] - centre[0]) <= 1 and abs(icon["middle"][1] - centre[1]) <= 1, (icon, centre)


def test_a_press_on_the_visible_part_of_a_covered_icon_opens_its_own_station(page_at: Callable[[float, float], Page],
                                                                            net: Net) -> None:
    # SPEC-0006 REQ-005, AC-006: two icons half over each other — Leaflet lays the southern one on top. A press on the
    # part of the northern icon that still shows opens the northern station's window, not its neighbour's
    serve(net, [("socar", "SOCAR", "#e41e30"), ("lukoil", "Lukoil", "#8a1538")])
    spots = net.data["stations.json"]["companies"]  # type: ignore[index]
    # at the city view's zoom (12) a pixel is some 28 m here: Lukoil some 15 px south-east of SOCAR, so they overlap
    spots[0]["stations"][0].update(lat=HERE[0] + 0.010, lng=HERE[1])  # SOCAR — north
    spots[1]["stations"][0].update(lat=HERE[0] + 0.0061, lng=HERE[1] + 0.0052)  # Lukoil — south-east, drawn on top
    page = page_at(*HERE)
    page.clock.set_fixed_time(TIME)
    page.goto(net.base)
    page.get_by_text("დიზელი", exact=True).first.click()
    expect(page.locator(".station.near")).to_have_count(2)
    icons = {i["id"]: i for i in page.evaluate(ICONS_JS)}
    (sx, sy, sw, sh), (lx, ly, _, _) = icons["socar"]["box"], icons["lukoil"]["box"]
    assert icons["lukoil"]["z"] > icons["socar"]["z"], icons  # Lukoil is drawn over SOCAR
    assert sx + 8 <= lx < sx + sw and sy + 8 <= ly < sy + sh, icons  # they cover each other, SOCAR still shows
    page.mouse.click(sx + (lx - sx) / 2, sy + (ly - sy) / 2)  # on SOCAR's part that Lukoil leaves free
    expect(page.locator(".leaflet-popup-content")).to_contain_text("SOCAR")
    expect(page.locator(".leaflet-popup-content")).not_to_contain_text("Lukoil")


STAR_JS = """(s) => {
  const c = getComputedStyle(s), r = s.getBoundingClientRect();
  return { round: c.borderRadius, ground: c.backgroundColor, ink: c.color, text: s.textContent,
           frame: [c.borderTopStyle, parseFloat(c.borderTopWidth), c.borderTopColor], ring: c.boxShadow,
           size: [r.width, r.height], centre: [r.left + r.width / 2, r.top + r.height / 2],
           z: Number(c.zIndex) };
}"""
TOP_JS = "([x, y]) => !!document.elementFromPoint(x, y)?.closest('.best-pin')"


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_star_is_a_yellow_badge_on_the_cheapest_icons_corner(page_at: Callable[[float, float], Page], net: Net,
                                                                 scheme: str) -> None:
    # SPEC-0006 REQ-006, AC-007: a 22 px round yellow badge with a black ★, its #111111 frame 2 px as before and a
    # 1.5 px white ring round it; its middle 20 px right of and above the middle of SOCAR's icon (the cheapest here) —
    # on the icon's corner, clear of the logo's cut; above every icon; on any grey its yellow or its frame stands out
    page = open_near(page_at, net, FIVE, scheme)
    expect(page.locator("#best")).to_contain_text("SOCAR")
    page.wait_for_function(DRAWN, arg=".station img")
    star = page.locator(".best-pin")
    expect(star).to_have_count(1)
    got = star.evaluate(STAR_JS)
    assert (got["round"], got["ground"], got["ink"], got["text"]) == ("50%", "rgb(255, 197, 41)", "rgb(17, 17, 17)",
                                                                     "★"), got
    assert got["frame"] == ["solid", 2, "rgb(17, 17, 17)"], got
    assert got["ring"].startswith("rgb(255, 255, 255) 0px 0px 0px 1.5px"), got
    assert all(abs(v - STAR) <= 0.5 for v in got["size"]), got
    icons = {i["id"]: i for i in page.evaluate(ICONS_JS)}
    mx, my = icons["socar"]["middle"]
    assert abs(got["centre"][0] - (mx + STAR_SHIFT)) <= 1 and abs(got["centre"][1] - (my - STAR_SHIFT)) <= 1, got
    (socar,) = page.evaluate(DISCS_JS, '.station[data-company="socar"] .disc')
    x, y, w, h = socar["at"]  # the logo's cut, as drawn
    gap = math.dist(got["centre"], (min(max(got["centre"][0], x), x + w), min(max(got["centre"][1], y), y + h)))
    assert gap >= STAR / 2 + 1.5, (gap, got, socar["at"])  # the badge and its ring clear of the logo
    assert got["z"] > max(i["z"] for i in icons.values()), (got, icons)
    assert page.evaluate(TOP_JS, got["centre"]), got  # nothing lies over it
    for v in range(256):
        assert max(ratio(rgb(got["ground"]), (v, v, v)), ratio(rgb(got["frame"][2]), (v, v, v))) >= 3, (got, v)


def test_from_far_the_star_stands_on_its_stations_dot_and_comes_back_to_the_corner(
        page_at: Callable[[float, float], Page], net: Net) -> None:
    # SPEC-0006 REQ-006 (SPEC-0005 REQ-007 from farther away): when the city view is left the icons become dots and the
    # ★ moves onto the middle of its station's dot; back in the city view it is on the icon's corner again
    page = open_near(page_at, net, FIVE)
    expect(page.locator("#best")).to_contain_text("SOCAR")
    socar, star = page.locator('.station[data-company="socar"]'), page.locator(".best-pin")

    def offset() -> tuple[float, float]:
        sx, sy = socar.evaluate(POINT_JS)
        got = star.evaluate(STAR_JS)["centre"]
        return got[0] - sx, got[1] - sy

    dx, dy = offset()
    assert abs(dx - STAR_SHIFT) <= 1 and abs(dy + STAR_SHIFT) <= 1, (dx, dy)
    zoom(page, "out", 2)  # zoom 12 → 10: from farther away
    expect(page.locator(".station.near")).to_have_count(0)
    dx, dy = offset()
    assert abs(dx) <= 1 and abs(dy) <= 1, (dx, dy)
    zoom(page, "in", 2)
    expect(page.locator(".station.near")).to_have_count(len(FIVE))
    dx, dy = offset()
    assert abs(dx - STAR_SHIFT) <= 1 and abs(dy + STAR_SHIFT) <= 1, (dx, dy)


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
    # AC-004 (SPEC-0005 AC-007: all five places together): opening — the row, the map, the ★ card and the list —,
    # the company filter opened and closed, a company switched off and on, the city view left and come back to
    page = open_near(page_at, net, FIVE)
    expect(page.locator(".station.near .disc img")).to_have_count(len(FIVE))
    expect(page.locator("#best .disc img, #price-list .disc img")).to_have_count(1 + len(FIVE))
    page.locator("#filter-company").click()
    expect(page.locator("#panel-company .disc img")).to_have_count(len(FIVE))
    page.locator("#filter-company").click()
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


def five_places(page: Page) -> dict[str, dict[str, dict]]:
    """Every company circle drawn, by place and by company — the company panel opened to draw its own."""
    page.locator("#filter-company").click()
    expect(page.locator("#panel-company .option")).not_to_have_count(0)
    page.wait_for_function(DRAWN, arg=".disc img")
    places = {"row": "#companies .disc", "list": "#price-list .disc", "filter": "#panel-company .disc",
              "card": "#best .disc", "map": ".station .disc"}
    return {place: {d["id"]: d for d in page.evaluate(DISCS_JS, sel)} for place, sel in places.items()}


SIZES = {"row": 48, "list": 40, "filter": 32, "card": 32, "map": MAP_ICON}  # px — an icon in each place (REQ-005)


def test_two_companies_without_a_logo_are_letter_circles_in_all_five_places(
        page_at: Callable[[float, float], Page], net: Net) -> None:
    # SPEC-0005 AC-006: Lukoil's file answers 404 and Nova is not in our list — in the row, the list, the company
    # filter, the ★ card (Nova is the cheapest near) and on the map, each is the circle of that place in its colour
    # with its letter; the other companies keep their logos; switched off, a letter circle only fades
    net.files["logos/lukoil.png"] = (404, "text/plain", "")
    serve(net, [("nova", "Nova", "#2563eb"), *FIVE])  # the first company's price is the lowest
    page = page_at(*HERE)
    page.clock.set_fixed_time(TIME)
    page.goto(net.base)
    page.get_by_text("დიზელი", exact=True).first.click()
    expect(page.locator("#best .who strong")).to_have_text("Nova")
    expect(page.locator('#companies [data-company="lukoil"]')).to_have_text("L")  # its file has failed
    logos = dict(page.evaluate(LIST_JS))
    places = five_places(page)
    for place, size in SIZES.items():
        got = places[place]
        assert "nova" in got and (place == "card" or "lukoil" in got), (place, sorted(got))
        for cid, d in got.items():
            assert_icon(d, size)
            if cid == "nova":
                assert_letter(d, size, "N", "rgb(37, 99, 235)")  # #2563eb
            elif cid == "lukoil":
                assert_letter(d, size, "L", "rgb(138, 21, 56)")  # #8a1538
            else:
                assert_mark(d, logos[cid], size)
    page.keyboard.press("Escape")
    nova = page.locator('#companies [data-company="nova"]')
    nova.click()
    expect(nova).to_have_attribute("aria-pressed", "false")
    faded = nova.locator(".letter").evaluate("(l) => [getComputedStyle(l).filter, Number(getComputedStyle(l).opacity)]")
    assert faded[0] == "grayscale(1)" and 0.35 <= faded[1] <= 0.5, faded


def test_a_hostile_name_or_code_is_only_text_in_the_list_and_the_card(page_at: Callable[[float, float], Page],
                                                                      net: Net) -> None:
    # SPEC-0005 AC-007 in the list and the ★ card: codes like an object's own field, a path or nothing, and a name
    # with HTML — the name is text everywhere, a picture only for the exact code in our list, no request by them
    companies = [(cid, EVIL if i == 0 else f"Co{i}", "#e41e30") for i, cid in enumerate(HOSTILE)]
    serve(net, [*companies, ("socar", EVIL, "#e41e30")])  # "constructor", the first, is the cheapest near
    page = page_at(*HERE)
    page.clock.set_fixed_time(TIME)
    page.goto(net.base)
    page.get_by_text("დიზელი", exact=True).first.click()
    expect(page.locator(ROWS)).to_have_count(len(HOSTILE) + 1)
    expect(page.locator("#best .who strong")).to_have_text(EVIL)  # the name as text
    expect(page.locator(ROWS).first.locator(".price-name strong")).to_have_text(EVIL)
    page.wait_for_function(DRAWN, arg="#best img, #price-list img")
    srcs = page.locator("#best img, #price-list img").evaluate_all("(i) => i.map((x) => x.getAttribute('src'))")
    assert srcs == ["logos/socar.svg"], srcs  # SOCAR's line only
    expect(page.locator("#best script, #price-list script")).to_have_count(0)
    page.wait_for_load_state("networkidle")
    assert page.evaluate("window.__pwned") is None
    asked = {u[len(net.base):].split("?")[0] for u in net.requests if u.startswith(net.base)}
    assert {a for a in asked if a.startswith("logos/")} == {"logos/socar.svg"}, asked
    assert net.outside == []


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
