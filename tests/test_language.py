"""T7 — Georgian and English: every text the page writes exists in both languages, and the switch changes all of
it. What the companies' sites write (fuel and station names, addresses) is shown as they publish it.

SPEC-0001: REQ-009, REQ-010 (the map-tiles sentence), AC-008.
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from support import SITE, Net

MKHEDRULI = re.compile(r"[ა-ჿ]")
PAGE_TEXTS = "h1, legend, .chip span, #best h2, #best label, #best .to-prices, #price-table th, .prices h2, footer p"


def dictionaries(page: Page, net: Net) -> dict:
    page.goto(net.base)
    return page.evaluate("async () => (await import('./js/i18n.js')).TEXT")


def test_every_text_exists_in_both_languages(page: Page, net: Net) -> None:
    text = dictionaries(page, net)
    assert set(text) == {"ka", "en"}
    assert set(text["ka"]) == set(text["en"])
    for lang, words in text.items():
        for key, value in words.items():
            assert isinstance(value, str) and value.strip(), (lang, key)
    assert not any(MKHEDRULI.search(v) for v in text["en"].values())
    used = set(re.findall(r"""\bt\(\s*['"]([\w.]+)['"]""", (SITE / "js" / "app.js").read_text(encoding="utf-8")))
    used |= set(re.findall(r'data-i18n="([\w.]+)"', (SITE / "index.html").read_text(encoding="utf-8")))
    used |= {f"fuel.{k}" for k in ("regular", "premium", "super", "diesel", "lpg", "cng")}
    assert used <= set(text["ka"]), used - set(text["ka"])


def test_the_switch_turns_the_whole_page_english_and_back(page: Page, net: Net) -> None:
    net.data["cities.json"] = {"cities": [{"ka": "ქუთაისი", "en": "Kutaisi", "lat": 42.26791, "lng": 42.69459},
                                          {"ka": "ბათუმი", "en": "Batumi", "lat": 41.64077, "lng": 41.6306}]}
    page.goto(net.base)
    expect(page.locator("#city")).to_be_visible()  # no place was allowed: the city list is shown
    page.locator("#city").select_option(label="ბათუმი")  # the card fills in, its "all prices" link with it
    expect(page.locator("#best a.to-prices")).to_have_text("ყველა ფასი")
    page.get_by_role("button", name="ENG").click()
    expect(page.locator("#best a.to-prices")).to_have_text("All prices")
    expect(page.locator("html")).to_have_attribute("lang", "en")
    expect(page.locator("h1")).to_contain_text("Fuel prices")
    expect(page.locator(".chip span")).to_have_text(["Regular", "Premium", "Super", "Diesel", "LPG", "CNG"])
    expect(page.locator("#city option")).to_have_text(["—", "Batumi", "Kutaisi"])
    expect(page.locator("footer")).to_contain_text("OpenStreetMap")
    for text in page.locator(PAGE_TEXTS).all_inner_texts():
        assert not MKHEDRULI.search(text), text
    assert page.title() and not MKHEDRULI.search(page.title())
    page.get_by_role("button", name="ქარ").click()
    expect(page.locator("html")).to_have_attribute("lang", "ka")
    expect(page.locator("h1")).to_contain_text("საწვავის ფასები")
    expect(page.locator(".chip span").first).to_have_text("რეგულარი")


def test_the_page_says_how_the_map_tiles_are_loaded(page: Page, net: Net) -> None:
    page.goto(net.base)
    expect(page.locator("footer")).to_contain_text("რუკის სურათები")
    expect(page.locator("footer")).to_contain_text("შენი ზუსტი მდებარეობა არსად იგზავნება")
