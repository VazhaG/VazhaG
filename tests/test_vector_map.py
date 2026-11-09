"""PLAN-0006 T6 — the map's ground is OpenFreeMap's vector map (SPEC-0006 REQ-007; AC-008's main part).

MapLibre GL JS draws it inside Leaflet: "liberty" by day and "dark" at night, switched with the look, never through a
colour filter; its labels in the site's language — the Georgian name (else the place's own), the Latin name in English;
OpenFreeMap's credit in sight. The page runs under ADR-0013's exact CSP with no violation, asks no host but the site,
OpenFreeMap and OpenStreetMap, and its footer says where the map comes from. The tests serve a small style of their own
in OpenFreeMap's place (tests/support.py: vector_style) — never the network.

PLAN-0006 T7 — the fallback (REQ-007; AC-008's fallback cases): with no WebGL, a library file that is missing or does
not answer, a missing style, no map in 5 seconds, or a missing style on a look switch, the map shows OpenStreetMap's
tiles with their credit within 6 seconds (5 and 1 of margin) — darkened by a filter at night, as before.
"""

from __future__ import annotations

import json
import re
import time

import pytest
from playwright.sync_api import Page, expect

from support import CSP, GROUND_JS, ROAD_NUMBER, STYLES, TILE_HOST, VECTOR_HOST, Net, vector_answer

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


def test_the_credit_is_the_pages_own_text_never_the_tile_indexs_html(page: Page, net: Net) -> None:
    # SPEC-0001 REQ-008's rule for an outside text: OpenFreeMap's tile index is a file from elsewhere, so its credit
    # never goes into the page as HTML — the page writes its own (ADR-0013's words)
    index = json.loads(vector_answer("planet")[2])
    index["attribution"] = ('<a href="https://prize.example/">Win a prize</a>'
                            '<img src="data:," onerror="window.__pwned = 1">')
    net.vector["planet"] = (200, "application/json", json.dumps(index))
    open_map(page, net)
    credit = page.locator(".leaflet-control-attribution")
    expect(credit).to_contain_text(CREDIT)
    expect(credit).not_to_contain_text("Win a prize")
    expect(credit.locator("img")).to_have_count(0)
    links = set(credit.locator("a").evaluate_all("(links) => links.map((a) => a.href)"))
    assert links <= CREDIT_LINKS | {"https://leafletjs.com/"}, links


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


# T7 — the fallback (REQ-007; AC-008)

LIBRARY = "vendor/maplibre/maplibre-gl.mjs"
OSM_CREDIT = "© OpenStreetMap contributors"
FALLBACK_WITHIN = 6  # seconds from the page's opening: REQ-007's 5 and 1 of margin (AC-008)
# a browser without WebGL: every WebGL drawing context is refused
NO_WEBGL = """(() => {
  const get = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (kind, ...rest) {
    return /webgl/i.test(kind) ? null : get.call(this, kind, ...rest);
  };
})();"""


def no_webgl(page: Page, net: Net, look: str) -> None:
    page.add_init_script(NO_WEBGL)


def library_missing(page: Page, net: Net, look: str) -> None:
    net.files[LIBRARY] = (404, "text/plain", "")


def library_silent(page: Page, net: Net, look: str) -> None:
    net.held.add(LIBRARY)


def style_missing(page: Page, net: Net, look: str) -> None:
    net.vector["styles/" + STYLES[look]] = (404, "text/plain", "")


def no_map_in_time(page: Page, net: Net, look: str) -> None:
    net.vector_held.add("planet/test/")  # the tiles never come: MapLibre's `load` never fires


def tile_index_failing(page: Page, net: Net, look: str) -> None:
    net.vector["planet"] = (503, "text/plain", "")  # MapLibre counts the source as loaded all the same (review C2)


def tiles_failing(page: Page, net: Net, look: str) -> None:
    net.vector_failing.add("planet/test/")


CAUSES = {"no WebGL": no_webgl, "the library missing": library_missing, "the library silent": library_silent,
          "the style missing": style_missing, "no map in 5 seconds": no_map_in_time,
          "the tile index failing": tile_index_failing, "the tiles failing": tiles_failing}
# a cause that is certain at once needs no wait: well before REQ-007's 5 seconds (the silent ones take those 5)
AT_ONCE = {"no WebGL", "the library missing", "the style missing", "the tile index failing", "the tiles failing"}
AT_ONCE_WITHIN = 4
# every value the map's data-ground takes, in order — a map that fell back on its first load never claimed the vector
GROUNDS_SEEN = """window.__grounds = [];
new MutationObserver(() => window.__grounds.push(document.getElementById('map').dataset.ground))
  .observe(document, { subtree: true, attributeFilter: ['data-ground'] });"""


def assert_fallback(page: Page, net: Net, look: str, started: float, within: float = FALLBACK_WITHIN) -> None:
    """OpenStreetMap's tiles with their credit in place of the vector map — darkened at night, never by day."""
    expect(page.locator("#map")).to_have_attribute("data-ground", "osm", timeout=within * 1000)
    assert time.monotonic() - started < within
    expect(page.locator(".leaflet-tile-pane .osm-tiles img.leaflet-tile-loaded").first).to_be_attached()
    assert any(u.startswith(TILE_HOST) for u in net.requests)
    credit = page.locator(".leaflet-control-attribution")
    expect(credit).to_contain_text(OSM_CREDIT)
    expect(credit).not_to_contain_text("OpenFreeMap")
    expect(page.locator(".leaflet-gl-layer")).to_have_count(0)
    tiles = page.locator(".osm-tiles").evaluate("(el) => getComputedStyle(el).filter")
    assert ("invert" in tiles) == (look == "dark"), tiles


@pytest.mark.parametrize("cause", CAUSES)
def test_the_map_falls_back_to_openstreetmap(page: Page, net: Net, cause: str) -> None:
    CAUSES[cause](page, net, "light")
    page.add_init_script(GROUNDS_SEEN)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.emulate_media(color_scheme="light")
    started = time.monotonic()
    page.goto(net.base)
    assert_fallback(page, net, "light", started, AT_ONCE_WITHIN if cause in AT_ONCE else FALLBACK_WITHIN)
    assert page.evaluate("window.__grounds") == ["osm"]  # never taken for a drawn vector map on the way
    page.wait_for_timeout(500)
    assert errors == []  # the vector map was taken off cleanly: nothing left throwing


def test_a_look_switch_undone_before_its_style_comes_keeps_each_looks_own_style(page: Page, net: Net) -> None:
    # review C1: ☾ and then ☀ before the dark style comes — when it comes, it neither shows on the light look nor is
    # kept as the light look's style
    net.vector_held.add("styles/dark")
    open_map(page, net, "light")
    page.locator("#theme").click()
    for _ in range(100):  # the dark style is on its way
        if net.stalled:
            break
        page.wait_for_timeout(50)
    page.locator("#theme").click()
    net.vector_held.clear()
    net.stalled.pop().fulfill(status=200, content_type="application/json", body=vector_answer("styles/dark")[2])
    page.wait_for_timeout(1000)
    assert ground(page)["style"] == "liberty"
    page.locator("#theme").click()
    until(page, "style", "dark")
    page.locator("#theme").click()
    until(page, "style", "liberty")
    assert styles_asked(net) == ["liberty", "dark"]


def test_a_style_on_its_way_is_asked_once_however_often_the_look_is_switched(page: Page, net: Net) -> None:
    net.vector_held.add("styles/dark")
    open_map(page, net, "light")
    for _ in range(3):  # ☾ ☀ ☾ while the dark style is on its way
        page.locator("#theme").click()
        page.wait_for_timeout(200)
    assert len(net.stalled) == 1, len(net.stalled)
    net.vector_held.clear()
    net.stalled.pop().fulfill(status=200, content_type="application/json", body=vector_answer("styles/dark")[2])
    until(page, "style", "dark")
    assert styles_asked(net) == ["liberty", "dark"]


def test_a_failing_picture_source_does_not_drop_the_vector_map(page: Page, net: Net) -> None:
    # only a vector source that fails leaves the map empty: the natural-earth pictures under it are a decoration
    net.vector_failing.add("natural_earth/")
    open_map(page, net)
    page.wait_for_load_state("networkidle")
    assert any(u.startswith(VECTOR_HOST + "natural_earth/") for u in net.requests)
    expect(page.locator("#map")).to_have_attribute("data-ground", "vector")


def test_the_map_asks_no_host_but_openfreemap_whatever_its_files_name(page: Page, net: Net) -> None:
    # review S1: the page's CSP does not reach MapLibre's worker, which fetches tiles and data itself — so the page
    # keeps every address a style or a tile index names on OpenFreeMap's host
    index = json.loads(vector_answer("planet")[2])
    index["tiles"] = ["https://tiles.example.net/{z}/{x}/{y}.pbf"]
    net.vector["planet"] = (200, "application/json", json.dumps(index))
    style = json.loads(vector_answer("styles/liberty")[2])
    style["sources"]["elsewhere"] = {"type": "geojson", "data": "https://data.example.net/points.json"}
    style["layers"].append({"id": "elsewhere", "type": "circle", "source": "elsewhere"})
    net.vector["styles/liberty"] = (200, "application/json", json.dumps(style))
    page.goto(net.base)
    expect(page.locator("#map")).to_have_attribute("data-ground", re.compile(r"^(vector|osm)$"))
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)
    assert net.outside == []


def test_a_library_that_comes_after_the_fallback_does_not_bring_the_vector_map_back(page: Page, net: Net) -> None:
    library_silent(page, net, "light")
    page.goto(net.base)
    expect(page.locator("#map")).to_have_attribute("data-ground", "osm", timeout=FALLBACK_WITHIN * 1000)
    net.pending.pop(LIBRARY).continue_()  # the library arrives at last
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)
    expect(page.locator("#map")).to_have_attribute("data-ground", "osm")
    expect(page.locator(".leaflet-gl-layer")).to_have_count(0)
    expect(page.locator(".leaflet-control-attribution")).not_to_contain_text("OpenFreeMap")


def test_with_no_webgl_the_library_is_not_even_asked_for(page: Page, net: Net) -> None:
    no_webgl(page, net, "dark")
    page.emulate_media(color_scheme="dark")
    started = time.monotonic()
    page.goto(net.base)
    assert_fallback(page, net, "dark", started)  # at night the fallback tiles are darkened, as before
    assert not [u for u in net.requests if "/vendor/maplibre" in u or u.startswith(VECTOR_HOST)]  # nothing to fetch


def test_a_missing_style_on_a_look_switch_falls_back_too(page: Page, net: Net) -> None:
    style_missing(page, net, "dark")
    open_map(page, net, "light")
    page.locator("#theme").click()
    assert_fallback(page, net, "dark", time.monotonic())


def test_after_the_fallback_the_tiles_follow_the_look(page: Page, net: Net) -> None:
    style_missing(page, net, "light")
    page.emulate_media(color_scheme="light")
    page.goto(net.base)
    expect(page.locator("#map")).to_have_attribute("data-ground", "osm")
    tiles = page.locator(".osm-tiles")
    page.locator("#theme").click()
    assert "invert" in tiles.evaluate("(el) => getComputedStyle(el).filter")
    page.locator("#theme").click()
    assert tiles.evaluate("(el) => getComputedStyle(el).filter") == "none"
    assert styles_asked(net) == ["liberty"]  # the vector map is not tried again
