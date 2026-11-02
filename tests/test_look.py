"""SPEC-0004 — the black-and-orange look (PLAN-0004); SPEC-0005 — the reference photo's colours (PLAN-0005 T2).

SPEC-0005 REQ-006 (PLAN-0005 T2) replaces T4's colours: the page and the header bar in the page colour (#F2F2F7 by
day, #1C1C1E at night); the sheet, the cards and the fuel chips on the surface colour (#FFFFFF, #2C2C2E) — so a
company circle's #8E8E93 frame keeps its 3 : 1 on the sheet (REQ-001); the text #111111 / #FFFFFF, the muted text
#5F5F64 / #A1A1A6, the lines #E5E5EA / #3A3A3C; in both looks the yellow accent #FFC529 with #111111 letters for the
chosen fuel and language (in bold too), Google Maps and Waze and the ★; a link in the text's colour, underlined.

T4: the colour roles of REQ-005 in both looks — the black header bar with a white title, orange main and chosen
buttons with black letters, the unchosen fuels on the sheet's colour in a neutral frame, the underlined links, the
muted text and the lines; the ★ mark orange with a black ★; the chosen fuel and language in bold letters too
(REQ-005; AC-003's ★, AC-008).
T5: the ☾/☀ switch in the header bar — a first visit follows the phone; the visitor's choice is kept on the phone and
wins over its setting; the page has its look before its first drawing; the colours, the map and the outlines follow
the site's look, not the phone's (REQ-005, REQ-006; AC-007, AC-008).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime

import pytest
from playwright.sync_api import Page, expect

from support import DISCS_JS, DRAWN, SITE, Net, assert_disc, assert_mark

TBILISI = (41.7151, 44.8271)
ROLES_JS = """() => {
  const css = (sel, prop) => { const el = document.querySelector(sel); return el && getComputedStyle(el)[prop]; };
  const chosen = '.chip input:checked + span', other = '.chip input:not(:checked) + span';
  const on = '.lang button[aria-pressed="true"]', off = '.lang button[aria-pressed="false"]';
  return {
    page: css('body', 'backgroundColor'), text: css('body', 'color'), sheet: css('.sheet', 'backgroundColor'),
    card: css('#best', 'backgroundColor'), header: css('.top', 'backgroundColor'), title: css('.top h1', 'color'),
    muted: css('.foot', 'color'), line: css('.prices', 'borderTopColor'),
    go: [css('.go a', 'backgroundColor'), css('.go a', 'color')],
    chosen: [css(chosen, 'backgroundColor'), css(chosen, 'color'), Number(css(chosen, 'fontWeight')) >= 700],
    other: [css(other, 'backgroundColor'), css(other, 'color'), css(other, 'borderTopStyle'),
            Number(css(other, 'fontWeight')) < 700],
    langOn: [css(on, 'backgroundColor'), css(on, 'color'), Number(css(on, 'fontWeight')) >= 700],
    langOff: [css(off, 'color'), Number(css(off, 'fontWeight')) < 700],
    link: [css('.to-prices', 'color'), css('.to-prices', 'textDecorationLine')],
    star: [css('.best-pin', 'backgroundColor'), css('.best-pin', 'color'), document.querySelector('.best-pin')?.textContent],
  };
}"""
WHITE, INK, YELLOW = "rgb(255, 255, 255)", "rgb(17, 17, 17)", "rgb(255, 197, 41)"  # #FFFFFF, #111111, #FFC529
DAY_PAGE, NIGHT_PAGE, NIGHT_SURFACE = "rgb(242, 242, 247)", "rgb(28, 28, 30)", "rgb(44, 44, 46)"
BOTH = {"go": [YELLOW, INK], "chosen": [YELLOW, INK, True], "langOn": [YELLOW, INK, True], "star": [YELLOW, INK, "★"]}
LOOKS = {
    "light": BOTH | {"page": DAY_PAGE, "text": INK, "sheet": WHITE, "card": WHITE, "header": DAY_PAGE, "title": INK,
                     "muted": "rgb(95, 95, 100)", "line": "rgb(229, 229, 234)", "other": [WHITE, INK, "solid", True],
                     "langOff": [INK, True], "link": [INK, "underline"]},
    "dark": BOTH | {"page": NIGHT_PAGE, "text": WHITE, "sheet": NIGHT_SURFACE, "card": NIGHT_SURFACE, "header": NIGHT_PAGE,
                    "title": WHITE, "muted": "rgb(161, 161, 166)", "line": "rgb(58, 58, 60)",
                    "other": [NIGHT_SURFACE, WHITE, "solid", True], "langOff": [WHITE, True], "link": [WHITE, "underline"]},
}


def open_look(page_at: Callable[[float, float], Page], net: Net, scheme: str) -> Page:
    """The real data at its own time, in Tbilisi: the ★ card, its links and the ★ on the map."""
    net.real_data = True
    page = page_at(*TBILISI)
    generated = json.loads((SITE / "data" / "prices.json").read_text(encoding="utf-8"))["generated"]
    page.clock.set_fixed_time(datetime.fromisoformat(generated))
    page.emulate_media(color_scheme=scheme)
    page.goto(net.base)
    expect(page.locator("#best a.go-google")).to_be_visible()
    expect(page.locator(".best-pin")).to_have_count(1)
    return page


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_each_colour_role_is_the_one_recorded(page_at: Callable[[float, float], Page], net: Net, scheme: str) -> None:
    # AC-008: every role of REQ-005, measured on the drawn page
    page = open_look(page_at, net, scheme)
    assert page.evaluate(ROLES_JS) == LOOKS[scheme]


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_star_card_shows_the_cheapest_companys_mark_in_its_circle(page_at: Callable[[float, float], Page],
                                                                      net: Net, scheme: str) -> None:
    # SPEC-0005 REQ-004, AC-001's card: on the real data, the cheapest company's mark in a 32 px circle; the compact
    # card 240 px high at most
    page = open_look(page_at, net, scheme)
    logos = dict(page.evaluate("() => import('./js/logos.js').then((m) => m.LOGOS.map((l) => [l.id, l.file]))"))
    page.wait_for_function(DRAWN, arg="#best .disc img")
    (d,) = page.evaluate(DISCS_JS, "#best .disc")
    assert_disc(d, 32)
    assert_mark(d, logos[d["id"]], 32)
    box = page.locator("#best").bounding_box()
    assert box and box["height"] <= 240, box


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_map_is_darkened_only_in_the_dark_look(page_at: Callable[[float, float], Page], net: Net,
                                                    scheme: str) -> None:
    # AC-008: the map's own pictures are darkened at night, never by day
    page = open_look(page_at, net, scheme)
    tiles = page.locator(".leaflet-tile-pane").evaluate("(el) => getComputedStyle(el).filter")
    assert ("invert" in tiles) == (scheme == "dark"), tiles


# T5 — the switch between the light and the dark look (REQ-005, REQ-006; AC-007, AC-008)
THEME = "#theme"
TIME = "2026-11-01T12:00:00Z"
STORAGE_KA = "ენა, კომპანიების არჩევანი და ნათელი თუ მუქი რეჟიმი მხოლოდ შენს ტელეფონში ინახება"
STORAGE_EN = "The language, your choice of companies and the light or dark mode are kept only on your phone"
BACKGROUND = "() => getComputedStyle(document.body).backgroundColor"
SIGN = "() => getComputedStyle(document.querySelector('#theme'), '::before').content"
LOOK = "() => document.documentElement.dataset.theme"
BLOCKED = ("Storage.prototype.getItem = Storage.prototype.setItem = Storage.prototype.removeItem ="
           " () => { throw new Error('blocked'); };")


def open_plain(page: Page, net: Net, phone: str, companies: list[dict] | None = None) -> None:
    net.data["prices.json"] = {"generated": TIME, "companies": companies or []}
    net.data["stations.json"] = {"generated": TIME, "companies": []}
    page.emulate_media(color_scheme=phone)
    page.goto(net.base)


@pytest.mark.parametrize("phone", ["light", "dark"])
def test_on_a_first_visit_the_look_follows_the_phone(page: Page, net: Net, phone: str) -> None:
    open_plain(page, net, phone)
    switch = page.locator(THEME)
    expect(switch).to_have_attribute("aria-pressed", "true" if phone == "dark" else "false")
    assert page.evaluate(SIGN) == ('"☀"' if phone == "dark" else '"☾"')  # where a press takes the page
    assert page.evaluate(LOOK) == phone
    assert page.evaluate(BACKGROUND) == (NIGHT_PAGE if phone == "dark" else DAY_PAGE)


def test_the_switch_changes_the_look_and_keeps_its_name_in_both_languages(page: Page, net: Net) -> None:
    # REQ-006: one name for a screen reader — "dark mode" — and aria-pressed says whether it is on
    open_plain(page, net, "light")
    switch = page.get_by_role("button", name="მუქი რეჟიმი", exact=True)
    expect(switch).to_have_attribute("aria-pressed", "false")
    switch.click()
    expect(switch).to_have_attribute("aria-pressed", "true")
    assert page.evaluate(SIGN) == '"☀"'
    assert page.evaluate(BACKGROUND) == NIGHT_PAGE
    page.get_by_role("button", name="ENG").click()
    switch = page.get_by_role("button", name="Dark mode", exact=True)
    expect(switch).to_have_attribute("aria-pressed", "true")
    switch.click()
    expect(switch).to_have_attribute("aria-pressed", "false")
    assert page.evaluate(SIGN) == '"☾"'
    assert page.evaluate(BACKGROUND) == DAY_PAGE


@pytest.mark.parametrize(("phone", "choice"), [("light", "dark"), ("dark", "light")])
def test_the_choice_is_kept_on_the_phone_and_wins_over_its_setting(page: Page, net: Net, phone: str,
                                                                  choice: str) -> None:
    open_plain(page, net, phone)
    page.locator(THEME).click()  # the opposite of the phone's setting
    assert page.evaluate("localStorage.getItem('fuel-map.theme')") == choice
    page.reload()
    expect(page.locator(THEME)).to_have_attribute("aria-pressed", "true" if choice == "dark" else "false")
    assert page.evaluate(LOOK) == choice
    tiles = page.locator(".leaflet-tile-pane").evaluate("(el) => getComputedStyle(el).filter")
    assert ("invert" in tiles) == (choice == "dark"), tiles  # AC-008: the map follows the site's look
    assert set(page.evaluate("Object.keys(localStorage)")) == {"fuel-map.theme"}
    assert net.bodies == [] and not [u for u in net.requests if "dark" in u or "light" in u]  # sent nowhere


@pytest.mark.parametrize(("phone", "choice", "edge"), [("dark", "light", "rgb(15, 23, 42)"),
                                                       ("light", "dark", "rgb(255, 255, 255)")])
def test_a_light_colours_outline_follows_the_sites_look(page: Page, net: Net, phone: str, choice: str,
                                                       edge: str) -> None:
    # SPEC-0003 REQ-003 by the site's look: a dark outline on a light colour's dot on the map in the light look only
    # (the row's circles have one neutral frame since SPEC-0005 REQ-001)
    connect = {"id": "connect", "name": "Connect", "color": "#ffe900", "source": "https://c.example/", "time": TIME,
               "basis": "read", "prices": [{"grade": "რეგულარი", "fuel": "regular", "price": 4.9}]}
    open_plain(page, net, phone, [connect])
    net.data["stations.json"] = {"generated": TIME, "companies": [connect | {"stations": [
        {"name": "", "address": "a", "lat": 41.7, "lng": 44.8, "fuels": ["regular"]}]}]}
    page.reload()  # no place allowed: the whole country's view, where a station is its colour's small dot
    page.locator(THEME).click()
    assert page.evaluate(LOOK) == choice
    dot = page.locator('.station[data-company="connect"]:not(.near) span')
    expect(dot).to_have_count(1)
    assert dot.evaluate("(s) => getComputedStyle(s).borderTopColor") == edge


def first_look(page: Page, net: Net, phone: str) -> str:
    """The look js/theme.js gives the page before the main script runs (the main script is held back)."""
    net.held.add("js/app.js")
    page.emulate_media(color_scheme=phone)
    page.goto(net.base, wait_until="commit")
    page.wait_for_function("() => document.documentElement.dataset.theme")
    return page.evaluate(LOOK)


@pytest.mark.parametrize("phone", ["light", "dark"])
@pytest.mark.parametrize("kept", ["purple", "", '{"theme": "dark"}', "DARK", " dark"])
def test_a_kept_value_that_is_not_a_choice_leaves_the_phones_setting(page: Page, net: Net, kept: str,
                                                                     phone: str) -> None:
    # REQ-006: only "light" or "dark" is a choice — for the first look (js/theme.js) and after (the main script)
    page.add_init_script(f"localStorage.setItem('fuel-map.theme', {json.dumps(kept)});")
    assert first_look(page, net, phone) == phone
    net.held.clear()
    open_plain(page, net, phone)
    assert page.evaluate(LOOK) == phone
    expect(page.locator(THEME)).to_have_attribute("aria-pressed", "true" if phone == "dark" else "false")


def test_with_the_storage_blocked_the_switch_still_works_on_this_visit(page: Page, net: Net) -> None:
    page.add_init_script(BLOCKED)
    open_plain(page, net, "light")
    page.locator(THEME).click()
    expect(page.locator(THEME)).to_have_attribute("aria-pressed", "true")
    assert page.evaluate(BACKGROUND) == NIGHT_PAGE


def test_a_kept_dark_look_is_there_before_the_main_script_runs(page: Page, net: Net) -> None:
    # AC-007: no flash of the light look — the main script stalls, and the page is already black
    page.add_init_script("localStorage.setItem('fuel-map.theme', 'dark');")
    net.held.add("js/app.js")
    page.emulate_media(color_scheme="light")
    page.goto(net.base, wait_until="commit")
    page.wait_for_timeout(3000)
    assert page.evaluate("document.querySelectorAll('#companies *').length") == 0  # the main script never ran
    assert page.evaluate(BACKGROUND) == NIGHT_PAGE
    assert page.evaluate(SIGN) == '"☀"'  # review C3: the switch already shows the dark look's sign
    # and before the first drawing: a plain script in <head>, ahead of the styles, so the browser waits for it
    head = (SITE / "index.html").read_text(encoding="utf-8").split("</head>")[0]
    assert '<script src="js/theme.js"></script>' in head, head
    assert head.index("js/theme.js") < head.index("css/style.css")


def test_the_page_says_what_it_keeps_on_the_phone(page: Page, net: Net) -> None:
    open_plain(page, net, "light")
    expect(page.locator("footer")).to_contain_text(STORAGE_KA)
    page.get_by_role("button", name="ENG").click()
    expect(page.locator("footer")).to_contain_text(STORAGE_EN)


# T6 — on a phone, and when the logos are missing or slow (AC-006, AC-009)
LOGO_FILES = ["logos/socar.svg", "logos/rompetrol.png", "logos/lukoil.png", "logos/wissol.svg", "logos/connect.png"]


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("language", ["ka", "en"])
def test_on_a_phone_the_card_the_row_and_both_switches_fit(page_at: Callable[[float, float], Page], net: Net,
                                                           scheme: str, language: str) -> None:
    # AC-009: 375 × 812 — the ★ card and "all prices" on the first screen, no sideways page, the five companies'
    # circles in one row that does not scroll (SPEC-0005 REQ-001), and the look switch and the language switch both
    # inside the header bar, clear of the title
    page = open_look(page_at, net, scheme)
    if language == "en":
        page.get_by_role("button", name="ENG").click()
        expect(page.locator("#best a.to-prices")).to_have_text("All prices")
    for target in ("#best", "#best a.to-prices"):
        box = page.locator(target).bounding_box()
        assert box and box["y"] + box["height"] <= 812, (target, box)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    expect(page.locator("#companies .badge")).to_have_count(5)
    assert page.locator("#companies").evaluate("(r) => r.scrollWidth <= r.clientWidth")
    bar, title = page.locator(".top").bounding_box(), page.locator(".top h1").bounding_box()
    assert bar and title and page.locator(".top h1").evaluate("(h) => h.scrollWidth <= h.clientWidth + 1")
    lines = page.locator(".top h1").evaluate("""(h) => { const r = document.createRange(); r.selectNodeContents(h);
      return new Set([...r.getClientRects()].map((x) => Math.round(x.top))).size; }""")
    assert lines == 1  # the title stays on one line beside the two switches
    for target in ("#theme", ".lang"):
        box = page.locator(target).bounding_box()
        assert box and box["x"] >= title["x"] + title["width"] and box["x"] + box["width"] <= 375, (target, box)
        assert box["y"] >= bar["y"] and box["y"] + box["height"] <= bar["y"] + bar["height"], (target, box)


@pytest.mark.parametrize("how", ["missing", "stalled"])
def test_without_any_logo_the_card_comes_within_10_seconds_and_the_row_stays(
        page_at: Callable[[float, float], Page], net: Net, how: str) -> None:
    # AC-006: every logo answers 404, or never answers; the page does not wait for them
    net.held.update(LOGO_FILES)  # first unanswered; "missing" answers them 404 once the row is measured
    net.real_data = True
    page = page_at(*TBILISI)
    generated = json.loads((SITE / "data" / "prices.json").read_text(encoding="utf-8"))["generated"]
    page.clock.set_fixed_time(datetime.fromisoformat(generated))
    page.goto(net.base, wait_until="domcontentloaded")  # a stalled picture holds the page's "load" back
    expect(page.locator("#best a.go-google")).to_be_visible(timeout=10_000)
    row = page.locator("#companies").bounding_box()
    if how == "missing":
        for file in LOGO_FILES:
            net.pending[file].fulfill(status=404, body="")
        expect(page.locator("#companies img")).to_have_count(0)  # every company is its letter circle now
    page.wait_for_timeout(1500)
    assert page.locator("#companies").bounding_box() == row  # the row stays where it is
