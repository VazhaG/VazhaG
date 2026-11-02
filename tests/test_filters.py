"""SPEC-0005 — the two filters on the map's top (PLAN-0005 T6).

T6: "კომპანია · 4/5" and "საწვავი · დიზელი" — two buttons on the map's top, as on the owner's reference photo, each 44 px
high at least, saying what is chosen; each opens its panel over the map (never over the ★ card): the company panel a
checkbox per company with its 32 px circle and name, which stays open; the fuel panel the six fuels to choose one,
which closes on the choice. Esc or a tap outside closes a panel and the focus returns to its button; the button says
aria-expanded. The filters change the same choice as the badge row and the fuel chips, and only the companies switched
off are kept on the phone (REQ-003; AC-001's filter, AC-003, AC-004).
"""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from playwright.sync_api import Page, expect

from support import DISCS_JS, DRAWN, Net, assert_disc, assert_mark

TIME = "2026-11-02T12:00:00Z"
HERE = (41.70, 44.80)
# Lukoil is the cheapest near, so switching it off moves the ★ (to SOCAR)
FIVE = [("socar", "SOCAR", "#e41e30", 4.90), ("rompetrol", "Rompetrol", "#f39200", 4.95),
        ("lukoil", "Lukoil", "#8a1538", 4.80), ("wissol", "Wissol", "#00843d", 5.05),
        ("connect", "Connect", "#ffe900", 5.00)]
COMPANY, FUEL = "#filter-company", "#filter-fuel"
COMPANY_PANEL, FUEL_PANEL = "#panel-company", "#panel-fuel"
ROWS = "#price-list li"
FOCUSED = "() => document.activeElement && (document.activeElement.id || document.activeElement.value)"


def serve(net: Net, companies: list[tuple[str, str, str, float]] = FIVE) -> None:
    """Each company: a diesel and a regular price, and one station a little north of the visitor that sells both."""
    prices, stations = [], []
    for i, (cid, name, color, diesel) in enumerate(companies):
        head = {"id": cid, "name": name, "color": color, "source": f"https://c{i}.example/", "time": TIME,
                "basis": "read"}
        prices.append(head | {"prices": [{"grade": f"{name} დიზელი", "fuel": "diesel", "price": diesel},
                                         {"grade": f"{name} რეგულარი", "fuel": "regular", "price": diesel - 1}]})
        stations.append(head | {"stations": [{"name": "", "address": "a", "lat": HERE[0] + (i + 1) / 300,
                                              "lng": HERE[1], "fuels": ["regular", "diesel"]}]})
    net.data["prices.json"] = {"generated": TIME, "companies": prices}
    net.data["stations.json"] = {"generated": TIME, "companies": stations}


def open_page(page_at: Callable[[float, float], Page], net: Net, scheme: str = "light") -> Page:
    serve(net)
    page = page_at(*HERE)
    page.emulate_media(color_scheme=scheme)
    page.clock.set_fixed_time(TIME)
    page.goto(net.base)
    expect(page.locator("#best a.go-google")).to_be_visible()
    return page


def stored(page: Page) -> dict:
    return page.evaluate("() => Object.fromEntries(Object.entries(localStorage))")


@pytest.mark.parametrize("language", ["ka", "en"])
def test_two_filters_on_the_maps_top_say_what_is_chosen(page_at: Callable[[float, float], Page], net: Net,
                                                        language: str) -> None:
    # REQ-003: the two buttons over the map's top, 44 px high at least, each its name and what is chosen; closed
    page = open_page(page_at, net)
    if language == "en":
        page.get_by_role("button", name="ENG").click()
    names = {"ka": ("კომპანია · 5/5", "საწვავი · რეგულარი"), "en": ("Company · 5/5", "Fuel · Regular")}[language]
    map_box = page.locator("#map").bounding_box()
    for selector, name in zip((COMPANY, FUEL), names, strict=True):
        button = page.locator(selector)
        expect(button).to_have_text(name)
        expect(page.get_by_role("button", name=name, exact=True)).to_have_count(1)
        expect(button).to_have_attribute("aria-expanded", "false")
        box = button.bounding_box()
        assert box and map_box and box["height"] >= 44, box
        assert map_box["y"] <= box["y"] and box["y"] + box["height"] <= map_box["y"] + 120, (box, map_box)  # on top
    for panel in (COMPANY_PANEL, FUEL_PANEL):
        expect(page.locator(panel)).to_be_hidden()
    chips = page.locator("#fuels").bounding_box()
    assert chips and chips["y"] >= page.locator(COMPANY).bounding_box()["y"] + 44  # the fuel chips under them


def test_the_company_panel_holds_each_company_with_its_circle_and_name(page_at: Callable[[float, float], Page],
                                                                      net: Net) -> None:
    # REQ-003, AC-001's filter: a checkbox per company, its 32 px circle and its name, each line 44 px at least; the
    # panel over the map, not over the ★ card
    page = open_page(page_at, net)
    logos = dict(page.evaluate("() => import('./js/logos.js').then((m) => m.LOGOS.map((l) => [l.id, l.file]))"))
    page.locator(COMPANY).click()
    panel = page.locator(COMPANY_PANEL)
    expect(panel).to_be_visible()
    expect(page.locator(COMPANY)).to_have_attribute("aria-expanded", "true")
    boxes = panel.get_by_role("checkbox")
    expect(boxes).to_have_count(len(FIVE))
    for i, (cid, name, *_) in enumerate(FIVE):
        expect(panel.get_by_role("checkbox", name=name, exact=True)).to_be_checked()
        line = panel.locator(f'[data-company="{cid}"]')
        box = line.bounding_box()
        assert box and box["height"] >= 44, (cid, box)
        expect(line).to_have_text(name)
        assert boxes.nth(i).get_attribute("value") == cid
    page.wait_for_function(DRAWN, arg=f"{COMPANY_PANEL} img")
    discs = page.evaluate(DISCS_JS, f"{COMPANY_PANEL} .disc")
    assert [d["id"] for d in discs] == [cid for cid, *_ in FIVE], discs  # one circle on each company's line
    for d in discs:
        assert_disc(d, 32)
        assert_mark(d, logos[d["id"]], 32)
    panel_box, card = panel.bounding_box(), page.locator("#best").bounding_box()
    sheet = page.locator(".sheet").bounding_box()
    assert panel_box and card and sheet and panel_box["y"] + panel_box["height"] <= min(card["y"], sheet["y"]), \
        (panel_box, card, sheet)


def test_a_company_switched_off_in_the_filter_is_off_everywhere_and_back_from_the_row(
        page_at: Callable[[float, float], Page], net: Net) -> None:
    # AC-003: Lukoil off in the filter — faded in the row, "4/5" on the button, gone from the map, the ★ and the list;
    # the panel stays open; switched on again in the row, it is checked in the filter; only fuel-map.off is kept
    page = open_page(page_at, net)
    page.get_by_text("დიზელი", exact=True).first.click()
    expect(page.locator("#best .who strong")).to_have_text("Lukoil")
    page.locator(COMPANY).click()
    page.locator(COMPANY_PANEL).get_by_role("checkbox", name="Lukoil", exact=True).uncheck()
    expect(page.locator('#companies [data-company="lukoil"]')).to_have_attribute("aria-pressed", "false")
    expect(page.locator(COMPANY)).to_have_text("კომპანია · 4/5")
    expect(page.locator('.station[data-company="lukoil"]')).to_have_count(0)
    expect(page.locator("#best .who strong")).to_have_text("SOCAR")
    expect(page.locator(ROWS)).to_have_count(4)
    expect(page.locator("#price-list")).not_to_contain_text("Lukoil")
    expect(page.locator(COMPANY_PANEL)).to_be_visible()  # it stays open: several companies at a time
    expect(page.locator(COMPANY)).to_have_attribute("aria-expanded", "true")
    page.locator(COMPANY_PANEL).get_by_role("checkbox", name="Wissol", exact=True).uncheck()
    expect(page.locator(COMPANY)).to_have_text("კომპანია · 3/5")
    assert json.loads(stored(page)["fuel-map.off"]) == ["lukoil", "wissol"]
    page.locator('#companies [data-company="lukoil"]').click()  # on again, from the row
    expect(page.locator(COMPANY)).to_have_text("კომპანია · 4/5")
    page.locator(COMPANY).click()  # the row's click closed the panel; open it again
    expect(page.locator(COMPANY_PANEL).get_by_role("checkbox", name="Lukoil", exact=True)).to_be_checked()
    expect(page.locator(COMPANY_PANEL).get_by_role("checkbox", name="Wissol", exact=True)).not_to_be_checked()
    assert set(stored(page)) == {"fuel-map.off"}


def test_every_company_off_in_the_filter_says_to_turn_one_on(page_at: Callable[[float, float], Page],
                                                             net: Net) -> None:
    page = open_page(page_at, net)
    page.locator(COMPANY).click()
    for box in page.locator(COMPANY_PANEL).get_by_role("checkbox").all():
        box.uncheck()
    expect(page.locator(COMPANY)).to_have_text("კომპანია · 0/5")
    expect(page.locator("#best")).to_contain_text("ჩართე ერთი კომპანია მაინც")
    expect(page.locator(ROWS)).to_have_count(0)
    expect(page.locator("#companies .badge[aria-pressed='true']")).to_have_count(0)


def test_a_fuel_chosen_in_the_filter_closes_it_and_moves_the_chips_and_the_list(
        page_at: Callable[[float, float], Page], net: Net) -> None:
    # AC-003: the panel closes on the choice and the focus is back on its button; the chips and the list follow, and
    # the other way round; the fuel is not kept on the phone
    page = open_page(page_at, net)
    page.locator(FUEL).click()
    expect(page.locator(FUEL_PANEL).get_by_role("radio")).to_have_count(6)
    expect(page.locator(FUEL_PANEL).get_by_role("radio", name="რეგულარი", exact=True)).to_be_checked()
    page.locator(FUEL_PANEL).get_by_role("radio", name="დიზელი", exact=True).click()
    expect(page.locator(FUEL_PANEL)).to_be_hidden()
    expect(page.locator(FUEL)).to_have_attribute("aria-expanded", "false")
    assert page.evaluate(FOCUSED) == "filter-fuel"
    expect(page.locator(FUEL)).to_have_text("საწვავი · დიზელი")
    expect(page.locator('#fuels input[value="diesel"]')).to_be_checked()
    expect(page.locator(ROWS).first).to_contain_text("დიზელი")
    page.locator("#fuels").get_by_text("რეგულარი", exact=True).click()  # the chips the other way round
    expect(page.locator(FUEL)).to_have_text("საწვავი · რეგულარი")
    page.locator(FUEL).click()
    expect(page.locator(FUEL_PANEL).get_by_role("radio", name="რეგულარი", exact=True)).to_be_checked()
    expect(page.locator(ROWS).first).to_contain_text("რეგულარი")
    assert stored(page) == {}  # nothing kept: every company on, and the fuel never


def test_the_filters_work_from_the_keyboard(page_at: Callable[[float, float], Page], net: Net) -> None:
    # AC-004: Enter opens, Tab reaches the boxes, Space changes one, Esc closes and the focus is back on the button;
    # in the fuel panel the arrows go through the fuels and Space chooses and closes
    page = open_page(page_at, net)
    page.locator(COMPANY).focus()
    page.keyboard.press("Enter")
    expect(page.locator(COMPANY)).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("Tab")
    assert page.evaluate(FOCUSED) == "socar"
    page.keyboard.press("Space")
    expect(page.locator('#companies [data-company="socar"]')).to_have_attribute("aria-pressed", "false")
    assert page.evaluate(FOCUSED) == "socar"  # the box keeps the focus
    page.keyboard.press("Tab")
    assert page.evaluate(FOCUSED) == "rompetrol"
    page.keyboard.press("Escape")
    expect(page.locator(COMPANY_PANEL)).to_be_hidden()
    expect(page.locator(COMPANY)).to_have_attribute("aria-expanded", "false")
    assert page.evaluate(FOCUSED) == "filter-company"
    page.locator(FUEL).focus()
    page.keyboard.press("Enter")
    page.keyboard.press("Tab")
    assert page.evaluate(FOCUSED) == "regular"
    page.keyboard.press("ArrowDown")  # through the fuels: the choice moves, the panel stays
    expect(page.locator(FUEL)).to_have_text("საწვავი · პრემიუმი")
    expect(page.locator(FUEL_PANEL)).to_be_visible()
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    expect(page.locator(FUEL)).to_have_text("საწვავი · დიზელი")
    page.keyboard.press("Space")  # review C1: Space on the fuel reached by the arrows ends the choice
    expect(page.locator(FUEL_PANEL)).to_be_hidden()
    assert page.evaluate(FOCUSED) == "filter-fuel"
    expect(page.locator('#fuels input[value="diesel"]')).to_be_checked()
    page.keyboard.press("Enter")  # and Esc, the other way out, closes it too
    page.keyboard.press("Tab")
    page.keyboard.press("Escape")
    expect(page.locator(FUEL_PANEL)).to_be_hidden()
    assert page.evaluate(FOCUSED) == "filter-fuel"


def test_a_tap_on_the_fuel_already_chosen_closes_the_panel(page_at: Callable[[float, float], Page],
                                                          net: Net) -> None:
    # review C1: the chosen fuel tapped again ends the choice as any other fuel does, and keeps it
    page = open_page(page_at, net)
    page.locator(FUEL).click()
    page.locator(FUEL_PANEL).get_by_role("radio", name="რეგულარი", exact=True).click()
    expect(page.locator(FUEL_PANEL)).to_be_hidden()
    expect(page.locator(FUEL)).to_have_text("საწვავი · რეგულარი")
    assert page.evaluate(FOCUSED) == "filter-fuel"


def test_a_tap_outside_closes_the_panel_and_the_focus_returns(page_at: Callable[[float, float], Page],
                                                              net: Net) -> None:
    # AC-004: a tap on the map closes the open panel; the other filter's button opens its own
    page = open_page(page_at, net)
    page.locator(COMPANY).click()
    expect(page.locator(COMPANY_PANEL)).to_be_visible()
    map_box = page.locator("#map").bounding_box()
    assert map_box
    page.mouse.click(map_box["x"] + 30, map_box["y"] + map_box["height"] - 60)  # the map, clear of the panel
    expect(page.locator(COMPANY_PANEL)).to_be_hidden()
    expect(page.locator(COMPANY)).to_have_attribute("aria-expanded", "false")
    assert page.evaluate(FOCUSED) == "filter-company"
    page.locator(COMPANY).click()
    page.locator(FUEL).click()  # one panel at a time
    expect(page.locator(COMPANY_PANEL)).to_be_hidden()
    expect(page.locator(FUEL_PANEL)).to_be_visible()
    expect(page.locator(COMPANY)).to_have_attribute("aria-expanded", "false")
    expect(page.locator(FUEL)).to_have_attribute("aria-expanded", "true")
    page.locator(FUEL).click()  # its own button closes it too
    expect(page.locator(FUEL_PANEL)).to_be_hidden()


def test_a_tap_far_down_the_page_closes_the_panel_without_scrolling_back(page_at: Callable[[float, float], Page],
                                                                         net: Net) -> None:
    # review C2: the company panel left open, the visitor reads the list further down and taps a line — the panel
    # closes, and the page stays where it is instead of jumping back up to the filter's button
    page = open_page(page_at, net)
    page.locator(COMPANY).click()
    expect(page.locator(COMPANY_PANEL)).to_be_visible()
    page.evaluate("document.querySelector('#price-list li:last-child')"
                  ".scrollIntoView({ block: 'center', behavior: 'instant' })")  # the page's own scrolling is smooth
    page.wait_for_timeout(300)
    before = page.evaluate("window.scrollY")
    assert before > 100, before
    page.locator("#price-list li").last.click()
    expect(page.locator(COMPANY_PANEL)).to_be_hidden()
    page.wait_for_timeout(300)
    assert abs(page.evaluate("window.scrollY") - before) <= 1, (before, page.evaluate("window.scrollY"))


def test_the_companies_come_into_an_open_panel_when_the_data_arrives(page_at: Callable[[float, float], Page],
                                                                     net: Net) -> None:
    # on a slow network the company panel may be opened before the data comes: it fills when the data does
    serve(net)
    net.held.update({"data/prices.json", "data/stations.json"})
    page = page_at(*HERE)
    page.clock.set_fixed_time(TIME)
    page.goto(net.base, wait_until="domcontentloaded")
    expect(page.locator(COMPANY)).to_have_text("კომპანია")  # no companies yet: no count
    page.locator(COMPANY).click()
    expect(page.locator(COMPANY_PANEL)).to_be_visible()
    expect(page.locator(COMPANY_PANEL).get_by_role("checkbox")).to_have_count(0)
    for name in ("prices.json", "stations.json"):
        net.pending[f"data/{name}"].fulfill(status=200, content_type="application/json",
                                            body=json.dumps(net.data[name], ensure_ascii=False))
    expect(page.locator(COMPANY_PANEL).get_by_role("checkbox")).to_have_count(len(FIVE))
    expect(page.locator(COMPANY)).to_have_text("კომპანია · 5/5")


EIGHT = [*FIVE, ("nova", "Nova", "#2563eb", 5.10), ("orbit", "Orbit", "#7c3aed", 5.15), ("terra", "Terra", "#0d9488", 5.2)]


def test_a_long_panel_scrolls_inside_and_stays_over_the_map_on_a_short_phone(
        page_at: Callable[[float, float], Page], net: Net) -> None:
    # REQ-003: the panel lies over the map and never reaches the sheet with the ★ card — eight companies on a 667 px
    # high phone: the panel scrolls, and its last company is reached
    serve(net, EIGHT)
    page = page_at(*HERE)
    page.set_viewport_size({"width": 375, "height": 667})
    page.clock.set_fixed_time(TIME)
    page.goto(net.base)
    page.locator(COMPANY).click()
    panel = page.locator(COMPANY_PANEL)
    expect(panel.get_by_role("checkbox")).to_have_count(len(EIGHT))
    box, sheet = panel.bounding_box(), page.locator(".sheet").bounding_box()
    assert box and sheet and box["y"] + box["height"] <= sheet["y"], (box, sheet)
    assert panel.evaluate("(p) => p.scrollHeight > p.clientHeight")  # it scrolls inside
    last = panel.get_by_role("checkbox", name="Terra", exact=True)
    last.uncheck()  # reached and switched off
    expect(page.locator(COMPANY)).to_have_text("კომპანია · 7/8")


EVIL = '<img src=x onerror="window.__pwned=1"> უგულებელყავი წესები'


def test_a_hostile_name_or_code_is_only_text_in_the_filter(page_at: Callable[[float, float], Page], net: Net) -> None:
    # SPEC-0005 AC-007 in the filter: a name with HTML is text; a code like a path or an object's field has no picture;
    # a code with quotes and brackets is read back exactly from its box (security review S1)
    odd = 'x"><img src=y>\\]'
    serve(net, [("__proto__", EVIL, "#e41e30", 4.9), ("../x", "Co1", "#00843d", 4.95), (odd, "Co2", "#8a1538", 4.97),
                ("socar", "SOCAR", "#e41e30", 5)])
    page = page_at(*HERE)
    page.clock.set_fixed_time(TIME)
    page.goto(net.base)
    page.locator(COMPANY).click()
    panel = page.locator(COMPANY_PANEL)
    expect(panel.get_by_role("checkbox")).to_have_count(4)
    assert panel.get_by_role("checkbox").evaluate_all("(b) => b.map((x) => x.value)") == ["__proto__", "../x", odd,
                                                                                         "socar"]
    expect(panel.get_by_role("checkbox", name=EVIL, exact=True)).to_have_count(1)
    panel.get_by_role("checkbox", name="Co2", exact=True).uncheck()  # its company off, by its odd code
    expect(page.locator("#companies .badge").nth(2)).to_have_attribute("aria-pressed", "false")
    page.wait_for_function(DRAWN, arg=f"{COMPANY_PANEL} img")
    srcs = panel.locator("img").evaluate_all("(i) => i.map((x) => x.getAttribute('src'))")
    assert srcs == ["logos/socar.svg"], srcs
    expect(panel.locator("script")).to_have_count(0)
    assert page.evaluate("window.__pwned") is None
    assert net.outside == []
