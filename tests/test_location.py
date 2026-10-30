"""T6 — no place from the phone: the visitor refused, or 10 seconds passed. The card offers the city list, and the
★ is counted from the chosen city's centre. The real list (site/data/cities.json) comes from GeoNames.

SPEC-0001: REQ-001, AC-003.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from playwright.sync_api import Browser, Page, expect

from support import PHONE, SITE, Net

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
KUTAISI = (42.26791, 42.69459)
CITIES = {"cities": [{"ka": "ქუთაისი", "en": "Kutaisi", "lat": KUTAISI[0], "lng": KUTAISI[1]},
                     {"ka": "ცუდი ჩანაწერი", "en": "Bad", "lat": "42.0", "lng": 43.0},  # a place must be a number
                     {"ka": "მოსკოვი", "en": "Moscow", "lat": 55.75, "lng": 37.62},  # outside Georgia
                     {"ka": "თბილისი", "en": "Tbilisi", "lat": 41.69143, "lng": 44.83412}]}
NEVER_ANSWERS = """navigator.geolocation.getCurrentPosition = () => {};"""


def data(net: Net) -> None:
    stamp = (NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    net.data["cities.json"] = CITIES
    net.data["prices.json"] = {"companies": [{"id": "a", "name": "ALPHA", "color": "#123456",
                                              "source": "https://a.example/", "time": stamp, "basis": "read",
                                              "prices": [{"grade": "ევრო დიზელი", "fuel": "diesel", "price": 4.97}]}]}
    near_kutaisi = {"name": "ქუთაისი 1", "address": "ქუთაისი", "lat": KUTAISI[0] + 0.01, "lng": KUTAISI[1],
                    "fuels": ["diesel"]}
    net.data["stations.json"] = {"companies": [{"id": "a", "name": "ALPHA", "color": "#123456",
                                                "source": "https://a.example/map", "time": stamp, "basis": "read",
                                                "stations": [near_kutaisi]}]}


def choose_kutaisi_and_see_its_station(page: Page) -> None:
    picker = page.locator("#city")
    expect(picker).to_be_visible()
    expect(picker.locator("option")).to_have_text(["—", "თბილისი", "ქუთაისი"])
    picker.select_option(label="ქუთაისი")
    page.get_by_text("დიზელი", exact=True).first.click()
    card = page.locator("#best")
    expect(card).to_contain_text("ქუთაისი 1")
    expect(card).to_contain_text("4.97 ₾")
    expect(card).to_contain_text("1.1 კმ")


def test_a_refused_location_offers_the_city_list(page: Page, net: Net) -> None:
    data(net)
    page.clock.set_fixed_time(NOW)
    page.goto(net.base)  # this browser was given no permission to the place: the request is refused
    expect(page.locator("#best")).to_contain_text("აირჩიე ქალაქი")
    choose_kutaisi_and_see_its_station(page)


def test_ten_seconds_without_an_answer_offers_the_city_list(browser: Browser, net: Net) -> None:
    data(net)
    context = browser.new_context(viewport=PHONE, locale="ka-GE")
    context.route("**/*", net.handle)
    context.add_init_script(NEVER_ANSWERS)
    page = context.new_page()
    page.clock.install(time=NOW)
    page.goto(net.base)
    page.clock.run_for(9_000)
    expect(page.locator("#city")).to_be_hidden()
    page.clock.run_for(1_500)
    choose_kutaisi_and_see_its_station(page)
    context.close()


def test_with_the_location_there_is_no_city_list(page_at: Callable[[float, float], Page], net: Net) -> None:
    data(net)
    page = page_at(*KUTAISI)
    page.goto(net.base)
    expect(page.locator("#best")).to_contain_text("★ ყველაზე იაფი ახლოს")
    expect(page.locator("#city")).to_have_count(0)


def test_the_real_city_list() -> None:
    cities = json.loads((SITE / "data" / "cities.json").read_text(encoding="utf-8"))
    assert "GeoNames" in cities["source"] and "CC BY 4.0" in cities["license"]
    names = {c["ka"] for c in cities["cities"]}
    assert len(cities["cities"]) == 73 == len(names)
    assert {"თბილისი", "ბათუმი", "ქუთაისი", "რუსთავი", "ზესტაფონი", "თეთრიწყარო"} <= names
    for c in cities["cities"]:
        assert 41.0 <= c["lat"] <= 43.7 and 39.9 <= c["lng"] <= 46.8, c
        assert c["en"] and all("ა" <= ch <= "ჿ" for ch in c["ka"]), c
