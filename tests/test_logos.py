"""SPEC-0004 — the companies' logos (PLAN-0004).

T1: five logo files inside the site, each the very bytes docs/domain/fuel-price-sources.md records, named in the page's
own list by the company's exact code; in the badge row a company with a logo shows it — one picture from our list, no
name text, on its own ground in a neutral frame, named for a screen reader (REQ-001, REQ-003; AC-001, AC-004).
"""

from __future__ import annotations

import hashlib
import re

import pytest
from playwright.sync_api import Page, expect

from support import LOGO_IDS, ROOT, SITE, Net

DOMAIN = ROOT / "docs" / "domain" / "fuel-price-sources.md"
TIME = "2026-11-01T12:00:00Z"
FIVE = [("socar", "SOCAR", "#e41e30"), ("rompetrol", "Rompetrol", "#f39200"), ("lukoil", "Lukoil", "#8a1538"),
        ("wissol", "Wissol", "#00843d"), ("connect", "Connect", "#ffe900")]
DARK_GROUND = {"socar", "connect"}  # REQ-001: SOCAR's letters are white, Connect's yellow is lost on white
BADGES = "#companies button.badge"
LIST_JS = "() => import('./js/logos.js').then((m) => m.LOGOS.map((l) => [l.id, l.file]))"
BADGE_JS = """(b) => {
  const s = getComputedStyle(b), r = b.getBoundingClientRect();
  return {
    imgs: [...b.querySelectorAll('img')].map((i) => [i.getAttribute('src'), i.complete && i.naturalWidth > 0,
                                                     getComputedStyle(i).filter, i.getAttribute('alt')]),
    pictures: b.querySelectorAll('svg, picture, object, embed, iframe').length,
    text: b.textContent.trim(), name: b.getAttribute('aria-label'), filter: s.filter,
    ground: s.backgroundColor, edge: s.borderTopColor, edgeWidth: s.borderTopWidth, width: r.width, height: r.height,
  };
}"""


def logo_list(page: Page, net: Net) -> dict[str, str]:
    """The page's own list, as the page reads it: company code -> file."""
    page.goto(net.base)
    return dict(page.evaluate(LIST_JS))


def recorded() -> dict[str, tuple[int, str]]:
    """Each company's logo — its size in bytes and its SHA-256 — as the domain document records it."""
    text = DOMAIN.read_text(encoding="utf-8")
    line = next(x for x in text.splitlines() if x.startswith("- ფაილების ბაიტები და SHA-256"))
    found = re.findall(r"(SOCAR|Rompetrol|Lukoil|Wissol|Connect)(?: `[^`]+`)? — ([\d\s]+) B, `([0-9a-f]{64})`", line)
    return {name.lower(): (int(re.sub(r"\D", "", size)), sha) for name, size, sha in found}


def test_each_logo_is_the_very_file_the_domain_document_records(page: Page, net: Net) -> None:
    # AC-004: a changed, swapped or re-encoded file is caught here
    logos = logo_list(page, net)
    want = recorded()
    assert sorted(logos) == sorted(want) == sorted(LOGO_IDS)
    for cid, file in logos.items():
        data = (SITE / file).read_bytes()
        assert (len(data), hashlib.sha256(data).hexdigest()) == want[cid], cid


def test_the_list_names_exactly_the_files_in_the_logo_folder(page: Page, net: Net) -> None:
    # AC-004: no file without its line, no line without its file — a removal takes both (REQ-004)
    logos = logo_list(page, net)
    files = sorted(p.relative_to(SITE).as_posix() for p in (SITE / "logos").iterdir())
    assert files == sorted(logos.values())
    assert all(re.fullmatch(r"logos/[a-z]+\.(?:svg|png)", f) for f in files), files
    assert sum((SITE / f).stat().st_size for f in files) <= 300_000  # REQ-003: 300 kB at most, all together


ADDRESS = re.compile(r"""(?:\b(?:xlink:)?href|\bsrc)\s*=\s*["']([^"']*)["']|url\(\s*["']?([^"')\s]*)""",
                     re.IGNORECASE)
FORBIDDEN = re.compile(r"<\s*script|<\s*foreignObject|@import|data:|javascript:|\son[a-z]+\s*=", re.IGNORECASE)


def test_an_svg_logo_holds_no_script_and_no_outside_address() -> None:
    # REQ-003: every href, xlink:href, src and url() points inside the file (#…); no script of any kind
    svgs = sorted((SITE / "logos").glob("*.svg"))
    assert [p.name for p in svgs] == ["socar.svg", "wissol.svg"]
    for svg in svgs:
        text = svg.read_text(encoding="utf-8")
        assert not FORBIDDEN.search(text), svg.name
        addresses = [a or b for a, b in ADDRESS.findall(text)]
        assert all(a.startswith("#") for a in addresses), (svg.name, addresses)


def open_five(page: Page, net: Net, scheme: str) -> None:
    prices = [{"id": cid, "name": name, "color": color, "source": f"https://{cid}.example/", "time": TIME,
               "basis": "read", "prices": [{"grade": "დიზელი", "fuel": "diesel", "price": 4.9}]}
              for cid, name, color in FIVE]
    net.data["prices.json"] = {"generated": TIME, "companies": prices}
    net.data["stations.json"] = {"generated": TIME, "companies": []}
    page.emulate_media(color_scheme=scheme)
    page.goto(net.base)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_each_company_with_a_logo_shows_it_on_its_badge(page: Page, net: Net, scheme: str) -> None:
    # AC-001: one picture from our list, loaded and drawn; no name text, no colour filter; the name for a screen
    # reader; the logo's own ground, the same in both looks; a thin neutral frame; 44 × 44 at least. The stylesheet
    # asks for 1.5 px (REQ-001); Chromium draws any width from 1 up to 2 px as 1 px, on every screen (PLAN-0004, T1)
    logos = logo_list(page, net)
    open_five(page, net, scheme)
    badges = page.locator(BADGES)
    expect(badges).to_have_count(len(FIVE))
    page.wait_for_function("() => [...document.querySelectorAll('#companies img')].every((i) => i.complete)")
    for i, (cid, name, _) in enumerate(FIVE):
        expect(badges.nth(i)).to_have_attribute("data-company", cid)
        got = badges.nth(i).evaluate(BADGE_JS)
        assert got["imgs"] == [[logos[cid], True, "none", ""]] and got["pictures"] == 0, (cid, got)
        assert (got["text"], got["name"], got["filter"]) == ("", name, "none"), (cid, got)
        assert got["ground"] == ("rgb(17, 17, 17)" if cid in DARK_GROUND else "rgb(255, 255, 255)"), (cid, got)
        assert got["edge"] == "rgb(107, 114, 128)" and 1 <= float(got["edgeWidth"][:-2]) < 2, (cid, got)
        assert got["width"] >= 44 and got["height"] >= 44, (cid, got)
        expect(page.get_by_role("button", name=name, exact=True)).to_have_count(1)
