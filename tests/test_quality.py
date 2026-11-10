"""T8 — privacy, speed and contrast, checked in a real browser on the real data files.

SPEC-0001: REQ-010, AC-010 (the visitor's place is in no request, nothing tracks), AC-001 (the ★ card within 10
seconds on a slow mobile network), §6 (text contrast WCAG AA, 4.5 : 1 — a hypothesis the owner approved with the spec).
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from datetime import datetime

import pytest
from playwright.sync_api import Page, expect

from support import CSP, SITE, Net, no_logos

# An odd place in Tbilisi, so its digits cannot turn up by chance in a station's or a tile's address.
VISITOR = (41.723457, 44.766531)
SLOW_4G = {"offline": False, "latency": 150, "downloadThroughput": 1.6 * 1024 * 1024 / 8,
           "uploadThroughput": 750 * 1024 / 8}  # Lighthouse's "slow 4G": 150 ms, 1.6 Mbit/s down, 750 kbit/s up


def at_data_time(page: Page) -> Page:
    """The page's clock at the moment the committed data was read, so its prices are fresh whatever today is — the
    repository copy is committed only when prices change (scraper/changed.py)."""
    generated = json.loads((SITE / "data" / "prices.json").read_text(encoding="utf-8"))["generated"]
    page.clock.set_fixed_time(datetime.fromisoformat(generated))
    return page


def visitor_traces() -> list[str]:
    lat, lng = VISITOR
    return [f"{lat}", f"{lng}", f"{lat:.4f}", f"{lng:.4f}", f"{lat:.3f}", f"{lng:.3f}", "723457", "766531"]


def test_the_visitors_place_never_leaves_the_page(page_at: Callable[[float, float], Page], net: Net) -> None:
    net.real_data = True
    page = at_data_time(page_at(*VISITOR))
    page.goto(net.base)
    card = page.locator("#best")
    expect(card.locator("a.go-google")).to_be_visible()
    page.get_by_text("პრემიუმი", exact=True).first.click()
    page.locator(".station").first.dispatch_event("click")  # it may lie outside the screen's part of the map
    expect(page.locator(".leaflet-popup-content a.go-waze")).to_be_visible()
    links = [a.get_attribute("href") or "" for a in page.locator("a.go-google, a.go-waze").all()]
    page.wait_for_load_state("networkidle")
    sent = net.requests + net.bodies + links
    for trace in visitor_traces():
        assert not [s for s in sent if trace in s], trace
    assert net.outside == []  # no script, font or beacon from anywhere else: only the site and the map images
    assert page.context.cookies() == []
    stored = page.evaluate("Object.keys(localStorage)")
    assert set(stored) <= {"fuel-map.lang", "fuel-map.off"}  # the language and the companies switched off (SPEC-0002)


WATCH_CSP = """window.__csp = [];
document.addEventListener('securitypolicyviolation', (e) => window.__csp.push(`${e.violatedDirective} ${e.blockedURI}`));"""


def test_the_page_runs_under_its_own_content_security_policy(page_at: Callable[[float, float], Page],
                                                             net: Net) -> None:
    # REQ-008 and REQ-010 do not rest on the code alone: the browser itself refuses the page a script, a style or a
    # request to any other place, should a later change let one in. MapLibre's worker is outside this rule (a worker
    # from the site's own file takes its policy from its own response, and the site sends none): js/vectormap.js keeps
    # its addresses on OpenFreeMap's host itself (tests/test_vector_map.py — review S1)
    net.real_data = True
    page = at_data_time(page_at(*VISITOR))
    page.add_init_script(WATCH_CSP)
    page.goto(net.base)
    expect(page.locator("meta[http-equiv='Content-Security-Policy']")).to_have_attribute("content", CSP)
    expect(page.locator("#best a.go-google")).to_be_visible()
    page.locator(".station").first.dispatch_event("click")
    expect(page.locator(".leaflet-popup-content a.go-waze")).to_be_visible()
    page.get_by_role("button", name="ENG").click()
    expect(page.locator("#best")).to_contain_text("Cheapest nearby")
    assert page.evaluate("window.__csp") == []
    page.evaluate("""() => { const s = document.createElement('script'); s.textContent = 'window.__ran = 1';
                             document.body.append(s); }""")
    page.wait_for_function("window.__csp.length > 0")
    assert page.evaluate("window.__ran") is None


@pytest.mark.parametrize("ground", ["the vector map on its way", "the library silent", "the style silent"])
def test_the_card_shows_within_10_seconds_on_a_slow_mobile_network(page_at: Callable[[float, float], Page],
                                                                    net: Net, ground: str) -> None:
    # SPEC-0006 AC-009: the ★ card never waits for the map's ground — loading, or stuck on its library or its style.
    # On this slow network the local server's uncompressed library (1.1 MB) takes longer than REQ-007's 5 seconds, so
    # in the first case the map itself ends on the fallback (measured 2026-11-09, review C-U1): the card's time is the
    # check here; the published site, which compresses the library, is measured after publishing (PLAN-0006 T8)
    net.real_data = True
    if ground == "the library silent":
        net.held.add("vendor/maplibre/maplibre-gl.mjs")
    if ground == "the style silent":
        net.vector_held.add("styles/")
    page = at_data_time(page_at(*VISITOR))
    cdp = page.context.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.emulateNetworkConditions", SLOW_4G)
    start = time.monotonic()
    page.goto(net.base)
    expect(page.locator(".leaflet-container")).to_be_visible(timeout=10_000)
    expect(page.locator("#best a.go-google")).to_be_visible(timeout=10_000)
    assert time.monotonic() - start < 10
    expect(page.locator("path.you")).to_have_count(1)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.wait_for_timeout(500)  # the map's ground starts once the card is drawn: its library is then asked for
    assert any(u.startswith(net.base + "vendor/maplibre/maplibre-gl.mjs") for u in net.requests)  # the vector map's way


CONTRAST_JS = """() => {
  const rgb = (s) => s.match(/[\\d.]+/g).map(Number);
  const lum = ([r, g, b]) => [r, g, b].map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; })
    .reduce((acc, v, i) => acc + v * [0.2126, 0.7152, 0.0722][i], 0);
  const background = (el) => {
    for (; el; el = el.parentElement) {
      const c = rgb(getComputedStyle(el).backgroundColor);
      if (c.length < 4 || c[3] > 0) return c.slice(0, 3);
    }
    return [255, 255, 255];
  };
  const out = [];
  for (const el of document.querySelectorAll(
      'h1, h2, .chip span, .lang button, #best p, #best label, .go a, .to-prices, #price-list p, #price-list .price, '
      + '#price-list .tag, '
      + '.foot p, .foot a, .leaflet-control-attribution, .leaflet-control-zoom a, .badge[aria-pressed="true"] .letter, '
      + '.station .letter')) {
    if (!el.textContent.trim() || !el.getClientRects().length) continue;
    const fg = rgb(getComputedStyle(el).color).slice(0, 3);
    const [a, b] = [lum(fg), lum(background(el))].sort((x, y) => y - x);
    out.push({ text: el.textContent.trim().slice(0, 30), ratio: (a + 0.05) / (b + 0.05) });
  }
  return out;
}"""


@pytest.mark.parametrize("logos", [True, False])  # SPEC-0004: the logos; without them, names and letters
@pytest.mark.parametrize("scheme", ["light", "dark"])  # the night look follows the phone (the owner, 2026-10-30)
def test_every_text_has_wcag_aa_contrast(page_at: Callable[[float, float], Page], net: Net, scheme: str,
                                         logos: bool) -> None:
    net.real_data = True
    if not logos:
        no_logos(net)
    page = at_data_time(page_at(*VISITOR))
    page.emulate_media(color_scheme=scheme)
    page.goto(net.base)
    expect(page.locator("#best a.go-google")).to_be_visible()
    page.get_by_text("დიზელი", exact=True).first.click()  # a chosen chip: black on yellow (SPEC-0005 REQ-006)
    if logos:
        expect(page.locator(".station.near .disc img").first).to_be_visible()  # the companies' marks on the map
    else:
        expect(page.locator(".station.near .letter").first).to_have_text(re.compile(r"\S"))  # letters on the map
    page.evaluate("document.querySelector('#price-list li:not(.cheap)')?.classList.add('stale')")  # a greyed-out line
    checked = page.evaluate(CONTRAST_JS)  # every company on: each colour as a letter circle and as letters on the map
    # a switched-off circle: its mark fades on purpose (SPEC-0005 REQ-002) — not text; its frame: test_logos.py
    page.locator("#companies .badge").first.click()
    expect(page.locator("#companies .badge").first).to_have_attribute("aria-pressed", "false")
    checked += page.evaluate(CONTRAST_JS)
    assert len(checked) > 40
    low = [c for c in checked if c["ratio"] < 4.5]
    assert low == [], low
