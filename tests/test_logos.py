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

import pytest
from playwright.sync_api import Page, expect

from support import LOGO_IDS, ROOT, SITE, Net

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


ADDRESS = re.compile(r"""(?:\b(?:xlink:)?href|\bsrc)\s*=\s*["']([^"']*)["']|url\(\s*["']?([^"')\s]*)""",
                     re.IGNORECASE)
FORBIDDEN = re.compile(r"<\s*script|<\s*foreignObject|@import|data:|javascript:|\son[a-z]+\s*=", re.IGNORECASE)


def test_an_svg_logo_holds_no_script_and_no_outside_address() -> None:
    # REQ-003: every href, xlink:href, src and url() points inside the file (#…); no script of any kind
    svgs = sorted((SITE / "logos").glob("*.svg"))
    assert [p.name for p in svgs] == ["socar.svg", "wissol.svg"]
    for svg in svgs:
        text = svg.read_text(encoding="utf-8")
        assert not FORBIDDEN.search(text), svg.name
        addresses = [a or b for a, b in ADDRESS.findall(text)]
        assert all(a.startswith("#") for a in addresses), (svg.name, addresses)


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
    page.wait_for_function("() => [...document.querySelectorAll('#companies img')].every((i) => i.complete)")
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


def test_only_an_exact_code_in_our_list_gets_a_picture_and_a_name_stays_text(page: Page, net: Net) -> None:
    # AC-005: codes that look like a path or an object's own field find nothing; the address is always our file
    companies = [(cid, EVIL if i == 0 else f"Co{i}", "#e41e30") for i, cid in enumerate(HOSTILE)]
    serve(net, [*companies, ("socar", EVIL, "#e41e30")])
    page.goto(net.base)
    expect(page.locator(BADGES)).to_have_count(len(HOSTILE) + 1)
    srcs = page.locator("#companies img").evaluate_all("(i) => i.map((x) => x.getAttribute('src'))")
    assert srcs == ["logos/socar.svg"]
    expect(page.locator(BADGES).first).to_have_text(EVIL)  # a name badge: the name as text only
    expect(page.locator('#companies [data-company="socar"]')).to_have_attribute("aria-label", EVIL)
    expect(page.get_by_role("button", name=EVIL)).to_have_count(2)
    expect(page.locator("#companies script")).to_have_count(0)
    page.wait_for_load_state("networkidle")
    assert page.evaluate("window.__pwned") is None
    allowed = {"", "css/style.css", "js/app.js", "js/i18n.js", "js/logic.js", "js/logos.js", "logos/socar.svg",
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
