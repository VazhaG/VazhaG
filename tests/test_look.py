"""SPEC-0004 — the black-and-orange look (PLAN-0004).

T4: the colour roles of REQ-005 in both looks — the black header bar with a white title, orange main and chosen
buttons with black letters, the unchosen fuels on the sheet's colour in a neutral frame, the underlined links, the
muted text and the lines; the ★ mark orange with a black ★; the chosen fuel and language in bold letters too
(REQ-005; AC-003's ★, AC-008).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime

import pytest
from playwright.sync_api import Page, expect

from support import SITE, Net

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
