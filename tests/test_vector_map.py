"""PLAN-0006 T6 — the map's ground is OpenFreeMap's vector map (SPEC-0006 REQ-007; AC-008's main part).

MapLibre GL JS draws it inside Leaflet: "liberty" by day and "dark" at night, switched with the look, never through a
colour filter; its labels in the site's language — the Georgian name (else the place's own), the Latin name in English;
OpenFreeMap's credit in sight. The page runs under ADR-0013's exact CSP with no violation, asks no host but the site,
OpenFreeMap and OpenStreetMap, and its footer says where the map comes from. The tests serve a small style of their own
in OpenFreeMap's place (tests/support.py: vector_style) — never the network.
"""

from __future__ import annotations

import time

import pytest
from playwright.sync_api import Page, expect

from support import CSP, GROUND_JS, ROAD_NUMBER, STYLES, VECTOR_HOST, Net

CREDIT = "OpenFreeMap © OpenMapTiles Data from OpenStreetMap"  # ADR-0013 §1
CREDIT_LINKS = {"https://openfreemap.org/", "https://www.openmaptiles.org/", "https://www.openstreetmap.org/copyright"}
# REQ-007: the Georgian name, else the place's own; in English, a Latin name
LABELS = {"ka": ["coalesce", ["get", "name:ka"], ["get", "name"]],
          "en": ["coalesce", ["get", "name:latin"], ["get", "name:en"]]}
LANG_BUTTON = {"ka": "ქარ", "en": "ENG"}
WATCH_CSP = """window.__csp = [];
document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(`${e.violatedDirective} ${e.blockedURI}`));"""


def ground(page: Page) -> dict:
    return page.evaluate(GROUND_JS)


def until(page: Page, check: str, value: object, timeout: float = 10) -> dict:
    """Wait until the ground's `check` reads `value` (MapLibre's state is read through a module, not the DOM)."""
    end = time.monotonic() + timeout
    while True:
        g = ground(page)
        if g[check] == value or time.monotonic() > end:
            assert g[check] == value, g
            return g
        page.wait_for_timeout(100)


def open_map(page: Page, net: Net, scheme: str = "light", lang: str | None = None) -> None:
    page.emulate_media(color_scheme=scheme)
    if lang:
        page.add_init_script(f"localStorage.setItem('fuel-map.lang', '{lang}')")
    page.goto(net.base)
    expect(page.locator("#map")).to_have_attribute("data-ground", "vector")


def styles_asked(net: Net) -> list[str]:
    return [u.removeprefix(VECTOR_HOST + "styles/") for u in net.requests if u.startswith(VECTOR_HOST + "styles/")]


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_ground_is_openfreemaps_vector_map_in_the_looks_style(page: Page, net: Net, scheme: str) -> None:
    open_map(page, net, scheme)
    g = ground(page)
    assert g["kind"] == "vector" and g["style"] == STYLES[scheme], g  # MapLibre's `load`: the style and first tiles
    assert styles_asked(net) == [STYLES[scheme]]  # the look's own style, asked once
    # drawn in Leaflet's tile pane — under the icons, the ★ and the buttons — over the whole map, with no colour filter
    assert g["covers"] and g["filters"] == [], g


def test_openfreemaps_credit_is_shown_with_its_links(page: Page, net: Net) -> None:
    open_map(page, net)
    credit = page.locator(".leaflet-control-attribution")
    expect(credit).to_contain_text(CREDIT)
    expect(credit).to_be_visible()
    assert CREDIT_LINKS <= set(credit.locator("a").evaluate_all("(links) => links.map((a) => a.href)"))


def test_the_vector_map_runs_under_the_exact_csp_and_asks_only_the_map_hosts(page: Page, net: Net) -> None:
    page.add_init_script(WATCH_CSP)
    open_map(page, net)
    expect(page.locator("meta[http-equiv='Content-Security-Policy']")).to_have_attribute("content", CSP)
    page.wait_for_load_state("networkidle")
    assert page.evaluate("window.__csp") == []
    assert net.outside == []
    assert {u.split("/")[2] for u in net.requests if not u.startswith(net.base)} <= {
        "tiles.openfreemap.org", "tile.openstreetmap.org"}
    # each kind of request the real style makes was met under the CSP: the style, the tile index and a tile, a
    # natural-earth picture, the sprite, the fonts — the Georgian letters' range among them; MapLibre's worker came
    # from the site itself
    asked = [u.removeprefix(VECTOR_HOST) for u in net.requests if u.startswith(VECTOR_HOST)]
    for kind in ("styles/liberty", "planet", "planet/test/", "natural_earth/", "sprites/", "fonts/"):
        assert any(a.startswith(kind) for a in asked), (kind, asked)
    assert any(a.endswith("/4096-4351.pbf") for a in asked), asked
    assert any(u.startswith(net.base + "vendor/maplibre/maplibre-gl-worker.mjs") for u in net.requests)


def test_a_look_switch_changes_the_maps_style(page: Page, net: Net) -> None:
    open_map(page, net, "light")
    page.locator("#theme").click()
    until(page, "style", "dark")
    page.locator("#theme").click()
    g = until(page, "style", "liberty")
    assert g["filters"] == [], g
    page.locator("#theme").click()
    until(page, "style", "dark")
    assert styles_asked(net) == ["liberty", "dark"]  # each look's style asked once, then kept


@pytest.mark.parametrize("first", ["ka", "en"])
def test_the_maps_labels_are_in_the_sites_language(page: Page, net: Net, first: str) -> None:
    open_map(page, net, lang=first)
    g = ground(page)
    assert g["labels"] == {"place_label": LABELS[first], "road_number": ROAD_NUMBER}, g
    other = "en" if first == "ka" else "ka"
    page.get_by_role("button", name=LANG_BUTTON[other]).click()
    g = until(page, "labels", {"place_label": LABELS[other], "road_number": ROAD_NUMBER})
    assert g["style"] == "liberty", g  # the same style, its labels rewritten


def test_the_footer_says_where_the_map_comes_from(page: Page, net: Net) -> None:
    page.goto(net.base)
    note = page.locator("#tiles-note")
    for lang in ("ka", "en"):
        page.get_by_role("button", name=LANG_BUTTON[lang]).click()
        expect(note).to_contain_text("OpenFreeMap")
        expect(note).to_contain_text("OpenStreetMap")
