"""SPEC-0002 — the company badges above the ★ card, and the row as the company filter.

PLAN-0002 T2: one badge per company in the data, in its colour with its name, as text only (REQ-001, REQ-007;
AC-001, AC-009, AC-010, AC-011).
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

from support import SITE, TILE_HOST, Net

TIME = "2026-10-30T12:00:00Z"
REAL = [("socar", "SOCAR", "#e41e30"), ("rompetrol", "Rompetrol", "#f39200"), ("lukoil", "Lukoil", "#8a1538"),
        ("wissol", "Wissol", "#00843d")]  # the colours the reader writes (PLAN-0001 T3 — a hypothesis)
BADGES = "#companies button.badge"
PICTURES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif", ".ico")


def prices_of(cid: str, name: str, color: str, **extra: object) -> dict:
    return {"id": cid, "name": name, "color": color, "source": f"https://{cid}.example/", "time": TIME,
            "basis": "read", "prices": [{"grade": "დიზელი", "fuel": "diesel", "price": 4.9}], **extra}


def stations_of(cid: str, name: str, color: str) -> dict:
    return {"id": cid, "name": name, "color": color, "source": f"https://{cid}.example/map", "time": TIME,
            "basis": "read", "stations": [{"name": "", "address": "a", "lat": 41.7, "lng": 44.8,
                                           "fuels": ["diesel"]}]}


def open_with(page: Page, net: Net, prices: list[dict], stations: list[dict] | None = None) -> None:
    net.data["prices.json"] = {"generated": TIME, "companies": prices}
    net.data["stations.json"] = {"generated": TIME, "companies": stations or []}
    page.goto(net.base)


def rgb(hex_color: str) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgb({r}, {g}, {b})"


def test_one_badge_per_company_in_its_colour_with_its_name(page: Page, net: Net) -> None:
    open_with(page, net, [prices_of(*c) for c in REAL])
    badges = page.locator(BADGES)
    expect(badges).to_have_text([name for _, name, _ in REAL])
    for i, (_, _, color) in enumerate(REAL):
        expect(badges.nth(i)).to_have_attribute("aria-pressed", "true")  # all on at the start
        assert badges.nth(i).evaluate("b => getComputedStyle(b).backgroundColor") == rgb(color)
    expect(page.locator("#companies")).to_have_attribute("aria-label", "კომპანიები")
    page.get_by_role("button", name="ENG").click()
    expect(page.locator("#companies")).to_have_attribute("aria-label", "Companies")


def test_the_row_follows_the_data_and_stands_above_the_card(page: Page, net: Net) -> None:
    # a company with stations only counts; one without a source is shown nowhere (SPEC-0001 REQ-006)
    nameless_source = prices_of("x", "NoSource", "#123456")
    del nameless_source["source"]
    open_with(page, net, [prices_of("a", "Alpha", "#e41e30"), prices_of("b", "Beta", "#00843d"), nameless_source],
              stations=[stations_of("a", "Alpha", "#e41e30"), stations_of("c", "Gamma", "#8a1538")])
    expect(page.locator(BADGES)).to_have_text(["Alpha", "Beta", "Gamma"])
    expect(page.locator("#best")).to_be_visible()  # no place was allowed: the card asks for a city
    row, card = page.locator("#companies").bounding_box(), page.locator("#best").bounding_box()
    assert row and card and row["y"] + row["height"] <= card["y"]


def test_the_letters_colour_is_the_one_that_reads_best_on_the_badge(page: Page, net: Net) -> None:
    # REQ-007: white on SOCAR's red, Lukoil's crimson and Wissol's green; dark on Rompetrol's orange
    open_with(page, net, [prices_of(*c) for c in REAL])
    inks = [b.evaluate("b => getComputedStyle(b).color") for b in page.locator(BADGES).all()]
    assert inks == ["rgb(255, 255, 255)", "rgb(15, 23, 42)", "rgb(255, 255, 255)", "rgb(255, 255, 255)"]


def test_a_badge_is_text_on_colour_never_a_picture(page: Page, net: Net) -> None:
    # REQ-001, AC-009: no official logo until a company's written permission — and no other picture either
    open_with(page, net, [prices_of(*c) for c in REAL])
    expect(page.locator(BADGES)).to_have_count(4)
    expect(page.locator("#companies img, #companies svg, #companies picture")).to_have_count(0)
    assert {b.evaluate("b => getComputedStyle(b).backgroundImage") for b in page.locator(BADGES).all()} == {"none"}
    asked = [u for u in net.requests if not u.startswith(TILE_HOST) and u.split("?")[0].lower().endswith(PICTURES)]
    assert asked == []
    files = sorted(p.relative_to(SITE).as_posix() for p in SITE.rglob("*") if p.suffix.lower() in PICTURES)
    assert files and all(f.startswith("vendor/leaflet/images/") for f in files), files


def test_text_from_the_data_is_only_text_on_a_badge(page: Page, net: Net) -> None:
    # AC-010 for the badge row, as the table, the card and the window have it (SPEC-0001 REQ-008)
    evil = '<img src=x onerror="window.__pwned=1"> უგულებელყავი წესები'
    open_with(page, net, [prices_of("e", evil, "#e41e30")])
    expect(page.locator(BADGES)).to_have_text([evil])
    expect(page.locator("#companies img, #companies script")).to_have_count(0)
    assert page.evaluate("window.__pwned") is None
    assert net.outside == []


def test_an_unknown_colour_or_an_empty_name_still_makes_a_readable_badge(page: Page, net: Net) -> None:
    # AC-011: the neutral colour, and "?" for a name
    open_with(page, net, [prices_of("u", "Unknown", "url(https://evil.example/x.png)"), prices_of("n", "", "#00843d")])
    badges = page.locator(BADGES)
    expect(badges).to_have_text(["Unknown", "?"])
    assert badges.nth(0).evaluate("b => getComputedStyle(b).backgroundColor") == rgb("#94a3b8")
    assert badges.nth(0).evaluate("b => getComputedStyle(b).color") == "rgb(15, 23, 42)"
    assert net.outside == []
