"""T8 — privacy, speed and contrast, checked in a real browser on the real data files.

SPEC-0001: REQ-010, AC-010 (the visitor's place is in no request, nothing tracks), AC-001 (the ★ card within 10
seconds on a slow mobile network), §6 (text contrast WCAG AA, 4.5 : 1 — a hypothesis the owner approved with the spec).
"""

from __future__ import annotations

import time
from collections.abc import Callable

from playwright.sync_api import Page, expect

from support import Net

# An odd place in Tbilisi, so its digits cannot turn up by chance in a station's or a tile's address.
VISITOR = (41.723457, 44.766531)
SLOW_4G = {"offline": False, "latency": 150, "downloadThroughput": 1.6 * 1024 * 1024 / 8,
           "uploadThroughput": 750 * 1024 / 8}  # Lighthouse's "slow 4G": 150 ms, 1.6 Mbit/s down, 750 kbit/s up


def visitor_traces() -> list[str]:
    lat, lng = VISITOR
    return [f"{lat}", f"{lng}", f"{lat:.4f}", f"{lng:.4f}", f"{lat:.3f}", f"{lng:.3f}", "723457", "766531"]


def test_the_visitors_place_never_leaves_the_page(page_at: Callable[[float, float], Page], net: Net) -> None:
    net.real_data = True
    page = page_at(*VISITOR)
    page.goto(net.base)
    card = page.locator("#best")
    expect(card.locator("a.go-google")).to_be_visible()
    page.get_by_text("პრემიუმი", exact=True).first.click()
    page.locator("path.station").first.dispatch_event("click")  # it may lie outside the screen's part of the map
    expect(page.locator(".leaflet-popup-content a.go-waze")).to_be_visible()
    links = [a.get_attribute("href") or "" for a in page.locator("a.go-google, a.go-waze").all()]
    page.wait_for_load_state("networkidle")
    sent = net.requests + net.bodies + links
    for trace in visitor_traces():
        assert not [s for s in sent if trace in s], trace
    assert net.outside == []  # no script, font or beacon from anywhere else: only the site and the map images
    assert page.context.cookies() == []
    stored = page.evaluate("Object.keys(localStorage)")
    assert set(stored) <= {"fuel-map.lang"}


def test_the_card_shows_within_10_seconds_on_a_slow_mobile_network(page_at: Callable[[float, float], Page],
                                                                    net: Net) -> None:
    net.real_data = True
    page = page_at(*VISITOR)
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
      'h1, h2, .chip span, .lang button, #best p, #best label, .go a, #price-table th, #price-table td, .foot p, .foot a')) {
    if (!el.textContent.trim() || !el.getClientRects().length) continue;
    const fg = rgb(getComputedStyle(el).color).slice(0, 3);
    const [a, b] = [lum(fg), lum(background(el))].sort((x, y) => y - x);
    out.push({ text: el.textContent.trim().slice(0, 30), ratio: (a + 0.05) / (b + 0.05) });
  }
  return out;
}"""


def test_every_text_has_wcag_aa_contrast(page_at: Callable[[float, float], Page], net: Net) -> None:
    net.real_data = True
    page = page_at(*VISITOR)
    page.goto(net.base)
    expect(page.locator("#best a.go-google")).to_be_visible()
    page.get_by_text("დიზელი", exact=True).first.click()  # a chosen chip: white on violet
    page.evaluate("document.querySelector('#price-table tbody tr')?.classList.add('stale')")  # a greyed-out row
    checked = page.evaluate(CONTRAST_JS)
    assert len(checked) > 20
    low = [c for c in checked if c["ratio"] < 4.5]
    assert low == [], low
