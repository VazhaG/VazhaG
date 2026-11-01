"""SPEC-0004 — the companies' logos (PLAN-0004).

T1: five logo files inside the site, each the very bytes docs/domain/fuel-price-sources.md records, named in the page's
own list by the company's exact code; in the badge row a company with a logo shows it — one picture from our list, no
name text, on its own ground in a neutral frame, named for a screen reader (REQ-001, REQ-003; AC-001, AC-004).
T2: switched off, a logo is grey, faded and crossed out; a company whose code is not exactly in our list, or whose file
fails, has its name badge, and a failed file is not asked for again on this visit (REQ-001, REQ-004; AC-002, AC-005,
AC-006).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from xml.etree import ElementTree

import pytest
from playwright.sync_api import Page, expect

from support import DRAWN, LOGO_IDS, ROOT, SITE, Net, logos_without

DOMAIN = ROOT / "docs" / "domain" / "fuel-price-sources.md"
TIME = "2026-11-01T12:00:00Z"
FIVE = [("socar", "SOCAR", "#e41e30"), ("rompetrol", "Rompetrol", "#f39200"), ("lukoil", "Lukoil", "#8a1538"),
        ("wissol", "Wissol", "#00843d"), ("connect", "Connect", "#ffe900")]
DARK_GROUND = {"socar", "connect"}  # REQ-001: SOCAR's letters are white, Connect's yellow is lost on white
BADGES = "#companies button.badge"
LIST_JS = "() => import('./js/logos.js').then((m) => m.LOGOS.map((l) => [l.id, l.file]))"
BADGE_JS = """(b) => {
  const s = getComputedStyle(b), r = b.getBoundingClientRect();
  return {
    imgs: [...b.querySelectorAll('img')].map((i) => [i.getAttribute('src'), i.complete && i.naturalWidth > 0,
                                                     getComputedStyle(i).filter, i.getAttribute('alt')]),
    pictures: b.querySelectorAll('svg, picture, object, embed, iframe').length,
    text: b.textContent.trim(), name: b.getAttribute('aria-label'), filter: s.filter,
    ground: s.backgroundColor, edge: s.borderTopColor, edgeWidth: s.borderTopWidth, width: r.width, height: r.height,
  };
}"""


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


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_each_company_with_a_logo_shows_it_on_its_badge(page: Page, net: Net, scheme: str) -> None:
    # AC-001: one picture from our list, loaded and drawn; no name text, no colour filter; the name for a screen
    # reader; the logo's own ground, the same in both looks; a thin neutral frame; 44 × 44 at least. The stylesheet
    # asks for 1.5 px (REQ-001); Chromium draws any width from 1 up to 2 px as 1 px, on every screen (PLAN-0004, T1)
    logos = logo_list(page, net)
    open_five(page, net, scheme)
    badges = page.locator(BADGES)
    expect(badges).to_have_count(len(FIVE))
    page.wait_for_function(DRAWN, arg="#companies img")
    for i, (cid, name, _) in enumerate(FIVE):
        expect(badges.nth(i)).to_have_attribute("data-company", cid)
        got = badges.nth(i).evaluate(BADGE_JS)
        assert got["imgs"] == [[logos[cid], True, "none", ""]] and got["pictures"] == 0, (cid, got)
        assert (got["text"], got["name"], got["filter"]) == ("", name, "none"), (cid, got)
        assert got["ground"] == ("rgb(17, 17, 17)" if cid in DARK_GROUND else "rgb(255, 255, 255)"), (cid, got)
        assert got["edge"] == "rgb(107, 114, 128)" and 1 <= float(got["edgeWidth"][:-2]) < 2, (cid, got)
        assert got["width"] >= 44 and got["height"] >= 44, (cid, got)
        expect(page.get_by_role("button", name=name, exact=True)).to_have_count(1)


# T2 — a switched-off logo, and the name badge when a logo cannot be shown (REQ-001, REQ-004; AC-002, AC-005, AC-006)
HERE = (41.70, 44.80)
ROWS = "#price-table tbody tr"
EVIL = '<img src=x onerror="window.__pwned=1"> უგულებელყავი წესები'
HOSTILE = ["constructor", "__proto__", "../x", "a/b.svg", ""]
OFF_JS = """(b) => {
  const img = b.querySelector('img'), line = getComputedStyle(b, '::after');
  return { filter: img && getComputedStyle(img).filter, opacity: img && Number(getComputedStyle(img).opacity),
           line: line.content, thick: line.height, ink: line.backgroundColor, turn: line.transform,
           ground: getComputedStyle(b).backgroundColor };
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


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_a_switched_off_logo_is_grey_faded_and_crossed_out_and_comes_back(page_at: Callable[[float, float], Page],
                                                                          net: Net, scheme: str) -> None:
    # AC-002 — on a light ground (Rompetrol) and on a dark one (SOCAR); the company leaves the map and the table
    serve(net, FIVE)
    page = page_at(*HERE)
    page.emulate_media(color_scheme=scheme)
    page.clock.set_fixed_time(TIME)
    page.goto(net.base)
    page.get_by_text("დიზელი", exact=True).first.click()
    for cid, name in (("rompetrol", "Rompetrol"), ("socar", "SOCAR")):
        badge, marks = page.locator(f'#companies [data-company="{cid}"]'), page.locator(f'.station[data-company="{cid}"]')
        expect(marks).to_have_count(1)
        expect(page.locator(ROWS)).to_have_count(5)
        on = badge.evaluate(OFF_JS)
        assert (on["filter"], on["opacity"], on["line"]) == ("none", 1, "none"), (cid, on)
        badge.click()
        expect(badge).to_have_attribute("aria-pressed", "false")
        off = badge.evaluate(OFF_JS)
        assert off["filter"] == "grayscale(1)" and 0.35 <= off["opacity"] <= 0.5, (cid, off)
        assert off["line"] != "none" and float(off["thick"][:-2]) >= 2 and off["turn"] != "none", (cid, off)
        assert ratio(rgb(off["ink"]), rgb(off["ground"])) >= 3, (cid, off)
        expect(marks).to_have_count(0)
        expect(page.locator(ROWS)).to_have_count(4)
        expect(page.locator("#price-table")).not_to_contain_text(name)
        badge.click()
        expect(badge).to_have_attribute("aria-pressed", "true")
        assert badge.evaluate(OFF_JS)["filter"] == "none"
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
    expect(page.locator(BADGES).first).to_have_text(EVIL)  # a name badge: the name as text only
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


def test_a_logo_that_does_not_load_leaves_a_name_badge_and_is_not_asked_again(page: Page, net: Net) -> None:
    # AC-006 and REQ-004: the others keep their logos; drawing the row anew does not ask for the failed file again
    net.files["logos/lukoil.png"] = (404, "text/plain", "")
    open_five(page, net, "light")
    lukoil = page.locator('#companies [data-company="lukoil"]')
    expect(lukoil).to_have_text("Lukoil")
    expect(lukoil.locator("img")).to_have_count(0)
    assert lukoil.evaluate("b => getComputedStyle(b).backgroundColor") == "rgb(138, 21, 56)"  # its colour
    expect(page.locator("#companies img")).to_have_count(4)
    socar = page.locator('#companies [data-company="socar"]')
    socar.click()  # the row is drawn anew, twice
    socar.click()
    expect(lukoil).to_have_text("Lukoil")
    assert [u for u in net.requests if u.endswith("/logos/lukoil.png")] == [f"{net.base}logos/lukoil.png"]


# T3 — the companies' marks on the map (REQ-002, REQ-003, REQ-004; AC-003, AC-004, AC-005)
MARKS_JS = """async () => {
  const { LOGOS } = await import('./js/logos.js');
  const byId = new Map(LOGOS.map((l) => [l.id, l]));
  return [...document.querySelectorAll('.station')].map((m) => {
    const logo = byId.get(m.dataset.company), frame = m.querySelector('span'), img = m.querySelector('img');
    const f = frame.getBoundingClientRect(), s = getComputedStyle(frame);
    const out = { id: m.dataset.company, near: m.classList.contains('near'), frame: [f.width, f.height],
                  ground: s.backgroundColor, round: s.borderRadius, text: frame.textContent,
                  imgs: m.querySelectorAll('img').length };
    if (img && logo) {
      const r = img.getBoundingClientRect(), k = r.width / logo.size[0], [x, y, w, h] = logo.mark;
      const left = r.left + x * k, top = r.top + y * k;
      const v = (getComputedStyle(img).clipPath.match(/[\\d.]+/g) || []).map(Number);
      // inset() is written like a margin: one, two, three or four values — top, right, bottom, left
      const [t, rt, b, lt] = [v[0], v[1] ?? v[0], v[2] ?? v[0], v[3] ?? v[1] ?? v[0]];
      const shown = v.length ? [r.left + lt, r.top + t, r.width - rt - lt, r.height - t - b] : null;
      Object.assign(out, { src: img.getAttribute('src'), alt: img.getAttribute('alt'), mark: [w * k, h * k],
                           clip: getComputedStyle(img).clipPath, shown, at: [left, top, w * k, h * k],
                           off: [left + w * k / 2 - (f.left + f.width / 2), top + h * k / 2 - (f.top + f.height / 2)],
                           loaded: img.complete && img.naturalWidth > 0,
                           inside: left >= f.left - 0.5 && top >= f.top - 0.5 && left + w * k <= f.right + 0.5
                                   && top + h * k <= f.bottom + 0.5 });
    }
    return out;
  });
}"""


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
def test_from_the_city_view_each_station_is_its_companys_mark_in_a_white_round_frame(
        page_at: Callable[[float, float], Page], net: Net, scheme: str) -> None:
    # AC-003: the mark is cut from the logo's own file; frame 28 px at least, the mark 22; a decoration (alt="")
    page = open_near(page_at, net, FIVE, scheme)
    logos = dict(page.evaluate(LIST_JS))
    page.wait_for_function(DRAWN, arg=".station img")
    marks = {m["id"]: m for m in page.evaluate(MARKS_JS)}
    for cid, *_ in FIVE:
        m = marks[cid]
        assert m["near"] and m["imgs"] == 1 and (m["src"], m["alt"], m["loaded"]) == (logos[cid], "", True), m
        assert min(m["frame"]) >= 28 and max(m["mark"]) >= 21.5 and m["inside"], m
        assert m["clip"].startswith("inset("), m  # only the mark shows through the frame
        assert max(abs(v) for v in m["off"]) <= 0.5, m  # in the middle of its frame
        assert m["shown"] and all(abs(a - b) <= 0.6 for a, b in zip(m["shown"], m["at"], strict=True)), m
        assert (m["ground"], m["round"], m["text"]) == ("rgb(255, 255, 255)", "50%", ""), m
    page.locator('.station[data-company="lukoil"]').dispatch_event("click")
    expect(page.locator(".leaflet-popup-content")).to_contain_text("Lukoil")  # the window names the company


def test_from_far_a_station_is_still_its_companys_small_dot(page: Page, net: Net) -> None:
    # AC-003: the whole country's view keeps the coloured dots (SPEC-0003 REQ-003), no picture
    serve(net, FIVE)
    page.clock.set_fixed_time(TIME)
    page.goto(net.base)  # no place allowed: the first view shows all of Georgia
    page.get_by_text("დიზელი", exact=True).first.click()  # the fuel the stations sell
    expect(page.locator(".station:not(.near)")).to_have_count(len(FIVE))
    marks = page.evaluate(MARKS_JS)
    assert all(not m["near"] and m["imgs"] == 0 and m["text"] == "" for m in marks), marks
    assert {m["id"]: m["ground"] for m in marks}["socar"] == "rgb(228, 30, 48)"  # SOCAR's colour, #e41e30


def test_each_logo_file_is_asked_once_whatever_the_row_and_the_map_do(page_at: Callable[[float, float], Page],
                                                                      net: Net) -> None:
    # AC-004: opening, switching a company off and on, leaving the city view and coming back
    page = open_near(page_at, net, FIVE)
    expect(page.locator(".station.near.logo")).to_have_count(len(FIVE))
    wissol = page.locator('#companies [data-company="wissol"]')
    wissol.click()
    wissol.click()
    zoom(page, "out", 3)
    expect(page.locator(".station.near")).to_have_count(0)
    zoom(page, "in", 3)
    expect(page.locator(".station.near.logo")).to_have_count(len(FIVE))
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
    expect(page.locator(".station.near:not(.logo) span")).to_have_text(["C"] * (len(companies) - 1))


def test_a_logo_that_fails_on_the_map_leaves_letter_circles_and_is_not_asked_again(
        page_at: Callable[[float, float], Page], net: Net) -> None:
    # REQ-004, AC-006 on the map
    net.files["logos/wissol.svg"] = (404, "text/plain", "")
    page = open_near(page_at, net, FIVE)
    expect(page.locator('.station[data-company="wissol"] span')).to_have_text("W")
    expect(page.locator('.station[data-company="wissol"] img')).to_have_count(0)
    expect(page.locator(".station.near.logo")).to_have_count(len(FIVE) - 1)
    zoom(page, "out", 3)
    zoom(page, "in", 3)
    expect(page.locator('.station[data-company="wissol"] span')).to_have_text("W")
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


def test_a_removed_logo_leaves_the_name_badge_and_the_letter_circle(page_at: Callable[[float, float], Page],
                                                                    net: Net) -> None:
    # AC-011: the file and its line taken out together (REQ-004) — the page no longer asks for the file
    net.files["js/logos.js"] = (200, "text/javascript", logos_without("lukoil"))
    net.files["logos/lukoil.png"] = (404, "text/plain", "")
    page = open_near(page_at, net, FIVE)
    expect(page.locator('#companies [data-company="lukoil"]')).to_have_text("Lukoil")
    expect(page.locator('.station[data-company="lukoil"] span')).to_have_text("L")
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
    expect(page.locator('#companies [data-company="wissol"]')).to_have_text("Wissol")
    expect(page.locator('.station[data-company="wissol"] span')).to_have_text("W")
    page.wait_for_timeout(300)  # past Leaflet's 200 ms fade: a closed window would be gone by now
    expect(page.locator(".leaflet-popup")).to_have_count(1)
    expect(page.locator(".leaflet-popup-content")).to_contain_text("SOCAR")
    assert page.evaluate("document.activeElement.dataset.company") == "rompetrol"
