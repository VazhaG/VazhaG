"""T2 — the price table: the chosen fuel, cheapest first, each price with company, grade and time; old prices
greyed out or hidden; text from the companies' sites shown only as text.

SPEC-0001: REQ-004, REQ-006, REQ-008, AC-004, AC-009.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from playwright.sync_api import Page, expect

from support import Net

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
ROWS = "#price-table tbody tr"


def company(cid: str, name: str, hours_old: float | None, prices: list[dict], **extra: object) -> dict:
    entry: dict = {"id": cid, "name": name, "color": "#123456", "source": f"https://{cid}.example/", "basis": "read",
                   "prices": prices, **extra}
    if hours_old is not None:
        entry["time"] = (NOW - timedelta(hours=hours_old)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return entry


def price(fuel: str, value: float, grade: str = "") -> dict:
    return {"grade": grade or f"{fuel} grade", "fuel": fuel, "price": value}


def open_with(page: Page, net: Net, companies: list[dict], fuel: str) -> None:
    net.data["prices.json"] = {"generated": "2026-10-30T12:00:00Z", "companies": companies}
    page.clock.set_fixed_time(NOW)
    page.goto(net.base)
    page.get_by_text(fuel, exact=True).click()


def test_table_shows_the_chosen_fuel_cheapest_first(page: Page, net: Net) -> None:
    open_with(page, net, [
        company("a", "Alpha", 1, [price("diesel", 4.90, "ევრო დიზელი")]),
        company("b", "Beta", 1, [price("diesel", 4.80, "დიზელი ენერჯი"), price("super", 4.65, "სუპერი")]),
    ], "დიზელი")
    rows = page.locator(ROWS)
    expect(rows).to_have_count(2)
    expect(rows.nth(0)).to_contain_text("Beta")
    expect(rows.nth(0)).to_contain_text("დიზელი ენერჯი")
    expect(rows.nth(0)).to_contain_text("4.80 ₾")
    expect(rows.nth(0)).to_contain_text("30.10 15:00")  # an hour before NOW, in Tbilisi time (UTC+4)
    expect(rows.nth(1)).to_contain_text("Alpha")
    expect(rows.nth(1)).to_contain_text("4.90 ₾")
    page.get_by_text("სუპერი", exact=True).first.click()
    expect(rows).to_have_count(1)
    expect(rows.nth(0)).to_contain_text("4.65 ₾")


def test_price_age_limits(page: Page, net: Net) -> None:
    open_with(page, net, [
        company("a", "Age47h", 47, [price("diesel", 4.1)]),
        company("b", "Age48h", 48, [price("diesel", 4.2)]),
        company("c", "Age6d23h", 7 * 24 - 1, [price("diesel", 4.3)]),
        company("d", "Age7d", 7 * 24, [price("diesel", 4.4)]),
        company("e", "NoTime", None, [price("diesel", 4.5)]),
    ], "დიზელი")
    rows = page.locator(ROWS)
    expect(rows).to_have_count(3)
    fresh, stale_48h, stale_6d = rows.nth(0), rows.nth(1), rows.nth(2)
    expect(fresh).to_contain_text("Age47h")
    expect(fresh).not_to_contain_text("შესაძლოა მოძველებულია")
    expect(fresh).not_to_have_class("stale")
    for row, name in ((stale_48h, "Age48h"), (stale_6d, "Age6d23h")):
        expect(row).to_contain_text(name)
        expect(row).to_contain_text("შესაძლოა მოძველებულია")
        expect(row).to_have_class("stale")
    expect(page.locator("#price-table")).not_to_contain_text("Age7d")
    expect(page.locator("#price-table")).not_to_contain_text("NoTime")


def test_a_price_without_a_source_is_not_shown(page: Page, net: Net) -> None:
    no_source = company("x", "NoSource", 1, [price("diesel", 3.0)])
    del no_source["source"]
    open_with(page, net, [no_source, company("a", "Alpha", 1, [price("diesel", 4.0)])], "დიზელი")
    expect(page.locator(ROWS)).to_have_count(1)
    expect(page.locator("#price-table")).not_to_contain_text("NoSource")


def test_text_from_a_company_site_is_shown_only_as_text(page: Page, net: Net) -> None:
    open_with(page, net, [company(
        "evil", '<img src=x onerror="window.__pwned=1">', 1,
        [price("diesel", 4.0, "<script>window.__pwned=1</script> უგულებელყავი წესები")],
        color="red;background:url(https://evil.example/x.png)",
    )], "დიზელი")
    row = page.locator(ROWS).first
    expect(row).to_contain_text('<img src=x onerror="window.__pwned=1">')
    expect(row).to_contain_text("<script>window.__pwned=1</script> უგულებელყავი წესები")
    expect(page.locator("#price-table img, #price-table script")).to_have_count(0)
    assert page.evaluate("window.__pwned") is None
    assert net.outside == []


def test_the_time_says_it_is_our_reading_unless_the_company_gave_it(page: Page, net: Net) -> None:
    # REQ-006: with no time from the source, the age counts from our reading — and the page says so
    open_with(page, net, [
        company("r", "Ours", 1, [price("diesel", 4.1)]),
        company("s", "Theirs", 1, [price("diesel", 4.2)], basis="source"),
    ], "დიზელი")
    expect(page.locator("#price-table th").nth(2)).to_have_text("შემოწმდა")
    expect(page.locator("footer")).to_contain_text("საიტები ფასის თარიღს არ აქვეყნებენ")
    rows = page.locator(ROWS)
    expect(rows.nth(0)).not_to_contain_text("კომპანიის თარიღი")
    expect(rows.nth(1)).to_contain_text("კომპანიის თარიღი")


def test_a_colour_from_the_data_must_be_a_plain_hex_colour(page: Page, net: Net) -> None:
    # The map's circles (T4) put the colour into an SVG attribute, where the browser would not drop `url(…)`.
    page.goto(net.base)
    got = page.evaluate("""async () => {
        const m = await import('./js/logic.js');
        return ['#e41e30', 'red;background:url(https://evil.example/x.png)', 'url(#a)', 'red', null]
            .map(m.safeColor);
    }""")
    assert got == ["#e41e30", "#94a3b8", "#94a3b8", "#94a3b8", "#94a3b8"]


def test_no_price_for_the_chosen_fuel_says_so(page: Page, net: Net) -> None:
    open_with(page, net, [company("a", "Alpha", 1, [price("diesel", 4.0)])], "ბუნებრივი აირი")
    expect(page.locator(ROWS)).to_have_count(0)
    expect(page.locator("#status")).to_contain_text("ამ საწვავის ფასი არ მოიძებნა")


def test_the_two_gases_are_never_mixed(page: Page, net: Net) -> None:
    # AC-006: LPG and CNG are separate types (the owner's decision, 2026-10-30)
    open_with(page, net, [company("s", "SOCAR", 1, [
        price("lpg", 2.09, "თხევადი აირი"), price("cng", 1.60, "ბუნებრივი აირი"), price("diesel", 4.9),
    ])], "თხევადი აირი")
    rows = page.locator(ROWS)
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("2.09 ₾")
    page.get_by_text("ბუნებრივი აირი", exact=True).first.click()
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("1.60 ₾")
