"""SPEC-0004 — the black-and-orange look (PLAN-0004).

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

from support import SITE, Net, no_logos

TBILISI = (41.7151, 44.8271)
ROLES_JS = """() => {
  const css = (sel, prop) => { const el = document.querySelector(sel); return el && getComputedStyle(el)[prop]; };
  const chosen = '.chip input:checked + span', other = '.chip input:not(:checked) + span';
  const on = '.lang button[aria-pressed="true"]', off = '.lang button[aria-pressed="false"]';
  return {
    page: css('body', 'backgroundColor'), text: css('body', 'color'), sheet: css('.sheet', 'backgroundColor'),
    header: css('.top', 'backgroundColor'), title: css('.top h1', 'color'),
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
WHITE, BLACK, ORANGE = "rgb(255, 255, 255)", "rgb(17, 17, 17)", "rgb(249, 115, 22)"
BOTH = {"header": BLACK, "title": WHITE, "go": [ORANGE, BLACK], "chosen": [ORANGE, BLACK, True],
        "langOn": [ORANGE, BLACK, True], "langOff": [WHITE, True], "star": [ORANGE, BLACK, "★"]}
LOOKS = {
    "light": BOTH | {"page": WHITE, "text": BLACK, "sheet": WHITE, "muted": "rgb(75, 85, 99)",
                     "line": "rgb(229, 231, 235)", "other": [WHITE, BLACK, "solid", True],
                     "link": ["rgb(194, 65, 12)", "underline"]},
    "dark": BOTH | {"page": "rgb(0, 0, 0)", "text": "rgb(245, 245, 245)", "sheet": BLACK, "muted": "rgb(163, 163, 163)",
                    "line": "rgb(42, 42, 42)", "other": [BLACK, "rgb(245, 245, 245)", "solid", True],
                    "link": ["rgb(251, 146, 60)", "underline"]},
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
    expect(switch).to_have_text("☀" if phone == "dark" else "☾")  # where a press takes the page
    assert page.evaluate(LOOK) == phone
    assert page.evaluate(BACKGROUND) == ("rgb(0, 0, 0)" if phone == "dark" else "rgb(255, 255, 255)")


def test_the_switch_changes_the_look_and_keeps_its_name_in_both_languages(page: Page, net: Net) -> None:
    # REQ-006: one name for a screen reader — "dark mode" — and aria-pressed says whether it is on
    open_plain(page, net, "light")
    switch = page.get_by_role("button", name="მუქი რეჟიმი", exact=True)
    expect(switch).to_have_attribute("aria-pressed", "false")
    switch.click()
    expect(switch).to_have_attribute("aria-pressed", "true")
    expect(switch).to_have_text("☀")
    assert page.evaluate(BACKGROUND) == "rgb(0, 0, 0)"
    page.get_by_role("button", name="ENG").click()
    switch = page.get_by_role("button", name="Dark mode", exact=True)
    expect(switch).to_have_attribute("aria-pressed", "true")
    switch.click()
    expect(switch).to_have_attribute("aria-pressed", "false")
    expect(switch).to_have_text("☾")
    assert page.evaluate(BACKGROUND) == "rgb(255, 255, 255)"


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
                                                       ("light", "dark", "rgb(255, 233, 0)")])
def test_a_light_colours_outline_follows_the_sites_look(page: Page, net: Net, phone: str, choice: str,
                                                       edge: str) -> None:
    # SPEC-0003 REQ-003 by the site's look: a dark outline on a light colour in the light look only
    no_logos(net)
    connect = {"id": "connect", "name": "Connect", "color": "#ffe900", "source": "https://c.example/", "time": TIME,
               "basis": "read", "prices": [{"grade": "დიზელი", "fuel": "diesel", "price": 4.9}]}
    open_plain(page, net, phone, [connect])
    page.locator(THEME).click()
    assert page.evaluate(LOOK) == choice
    badge = page.locator('#companies [data-company="connect"]')
    assert badge.evaluate("(b) => getComputedStyle(b).borderTopColor") == edge


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
    assert page.evaluate(BACKGROUND) == "rgb(0, 0, 0)"


def test_a_kept_dark_look_is_there_before_the_main_script_runs(page: Page, net: Net) -> None:
    # AC-007: no flash of the light look — the main script stalls, and the page is already black
    page.add_init_script("localStorage.setItem('fuel-map.theme', 'dark');")
    net.held.add("js/app.js")
    page.emulate_media(color_scheme="light")
    page.goto(net.base, wait_until="commit")
    page.wait_for_timeout(3000)
    assert page.evaluate("document.querySelectorAll('#companies *').length") == 0  # the main script never ran
    assert page.evaluate(BACKGROUND) == "rgb(0, 0, 0)"
    # and before the first drawing: a plain script in <head>, ahead of the styles, so the browser waits for it
    head = (SITE / "index.html").read_text(encoding="utf-8").split("</head>")[0]
    assert '<script src="js/theme.js"></script>' in head, head
    assert head.index("js/theme.js") < head.index("css/style.css")


def test_the_page_says_what_it_keeps_on_the_phone(page: Page, net: Net) -> None:
    open_plain(page, net, "light")
    expect(page.locator("footer")).to_contain_text(STORAGE_KA)
    page.get_by_role("button", name="ENG").click()
    expect(page.locator("footer")).to_contain_text(STORAGE_EN)
