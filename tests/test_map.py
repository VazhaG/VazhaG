"""T4 — the stations on the map: a circle in the company's colour for every station that sells the chosen fuel and has
a known place in Georgia.

SPEC-0001: REQ-001, REQ-002 (the choice changes the map), AC-002 (a station with an unknown place is not shown).
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

from support import Net

PETROL = ["regular", "premium", "super", "diesel"]
CIRCLES = "path.station"


def station(lat: object, lng: object, fuels: list[str], address: str = "მისამართი") -> dict:
    return {"name": "", "address": address, "lat": lat, "lng": lng, "fuels": fuels}


def stations_file(*companies: dict) -> dict:
    return {"generated": "2026-10-30T12:00:00Z", "companies": list(companies)}


def company(cid: str, color: str, stations: list[dict], **extra: object) -> dict:
    return {"id": cid, "name": cid.upper(), "color": color, "source": f"https://{cid}.example/map",
            "time": "2026-10-30T12:00:00Z", "basis": "read", "stations": stations, **extra}


def open_map(page: Page, net: Net, data: dict, fuel: str | None = None) -> None:
    net.data["stations.json"] = data
    page.goto(net.base)
    if fuel:
        page.get_by_text(fuel, exact=True).first.click()


def test_every_station_with_a_known_place_is_a_circle_in_its_company_colour(page: Page, net: Net) -> None:
    open_map(page, net, stations_file(
        company("a", "#e41e30", [station(41.70, 44.80, PETROL), station(41.64, 41.63, PETROL)]),
        company("b", "#00843d", [station(42.27, 42.70, PETROL)]),
    ))
    circles = page.locator(CIRCLES)
    expect(circles).to_have_count(3)
    fills = sorted(circles.nth(i).get_attribute("fill") or "" for i in range(3))
    assert fills == ["#00843d", "#e41e30", "#e41e30"]
    assert net.outside == []


def test_a_station_with_an_unknown_or_foreign_place_is_not_drawn(page: Page, net: Net) -> None:
    open_map(page, net, stations_file(company("a", "#e41e30", [
        station(41.70, 44.80, PETROL), station(None, 44.80, PETROL), station("41.7", "44.8", PETROL),
        station(0, 0, PETROL), station(55.75, 37.62, PETROL),
    ])))
    expect(page.locator(CIRCLES)).to_have_count(1)


def test_the_map_shows_only_stations_selling_the_chosen_fuel(page: Page, net: Net) -> None:
    open_map(page, net, stations_file(company("a", "#e41e30", [
        station(41.70, 44.80, PETROL), station(41.71, 44.81, ["regular", "diesel", "lpg"]),
        station(41.72, 44.82, ["cng"]),
    ])))
    circles = page.locator(CIRCLES)
    expect(circles).to_have_count(2)  # რეგულარი is chosen first
    page.get_by_text("თხევადი აირი", exact=True).first.click()
    expect(circles).to_have_count(1)
    page.get_by_text("ბუნებრივი აირი", exact=True).first.click()
    expect(circles).to_have_count(1)
    page.get_by_text("პრემიუმი", exact=True).first.click()
    expect(circles).to_have_count(1)


def test_a_company_without_a_source_or_with_a_bad_colour(page: Page, net: Net) -> None:
    no_source = company("x", "#e41e30", [station(41.70, 44.80, PETROL)])
    del no_source["source"]
    open_map(page, net, stations_file(no_source, company("y", "url(#evil)", [station(41.71, 44.81, PETROL)])))
    circles = page.locator(CIRCLES)
    expect(circles).to_have_count(1)
    assert circles.first.get_attribute("fill") == "#94a3b8"
