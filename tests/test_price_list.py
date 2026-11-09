"""SPEC-0005 — the price list in the table's place (PLAN-0005 T5).

T5: every price of the chosen fuel as a list, as on the owner's reference photo — one line per company's grade: the
company's 40 px circle, its name, the grade, when the price was read (with "the company's date" where the company gave
it) and the price; cheapest first, an equal price by the company's name; "იაფი" / "Cheapest" on a coloured ground for
every line with the lowest fresh price, never an old one; the list follows the fuel, and its messages stand in its
place (REQ-005, REQ-006; AC-005, AC-001's list).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from playwright.sync_api import Page, expect

from support import DISCS_JS, DRAWN, Net, assert_icon, assert_mark

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
ROWS = "#price-list li"
LIST_DISC = 40  # px — a company circle in the list (SPEC-0005 REQ-001)
READ_AT = "02.11 15:00"  # an hour before NOW, in Tbilisi time (UTC+4)
# (id, name, colour, hours old, whose time, prices: grade, fuel, price) — Connect sells two diesels, SOCAR's diesel
# costs what Connect's first one does, and Lukoil's old price is the lowest of all
COMPANIES = [
    ("socar", "SOCAR", "#e41e30", 1, "read", [("ნანო დიზელი", "diesel", 4.85), ("ნანო რეგულარი", "regular", 3.10)]),
    ("rompetrol", "Rompetrol", "#f39200", 1, "read", [("efix რეგულარი", "regular", 3.05)]),
    ("lukoil", "Lukoil", "#8a1538", 50, "read", [("ევრო დიზელი", "diesel", 4.50)]),
    ("wissol", "Wissol", "#00843d", 1, "source", [("ევრო დიზელი", "diesel", 4.95)]),
    ("connect", "Connect", "#ffe900", 1, "read", [("დიზელი", "diesel", 4.85), ("დიზელი ექსტრა", "diesel", 5.10)]),
]
# what the diesel list must be: company, grade, price, "cheapest", old
DIESEL = [("Lukoil", "ევრო დიზელი", "4.50 ₾", False, True), ("Connect", "დიზელი", "4.85 ₾", True, False),
          ("SOCAR", "ნანო დიზელი", "4.85 ₾", True, False), ("Wissol", "ევრო დიზელი", "4.95 ₾", False, False),
          ("Connect", "დიზელი ექსტრა", "5.10 ₾", False, False)]
LINES_JS = """(rows) => rows.map((r) => ({
  id: r.dataset.company, name: r.querySelector('.price-name strong')?.textContent,
  grade: r.querySelector('.grade')?.textContent, price: r.querySelector('.price')?.textContent,
  time: r.querySelector('.time')?.textContent, tag: r.querySelector('.tag')?.textContent ?? null,
  cheap: r.classList.contains('cheap'), stale: r.classList.contains('stale'), discs: r.querySelectorAll('.disc').length,
  ground: getComputedStyle(r).backgroundColor, height: r.getBoundingClientRect().height,
  tagColours: r.querySelector('.tag') && [getComputedStyle(r.querySelector('.tag')).backgroundColor,
                                          getComputedStyle(r.querySelector('.tag')).color,
                                          Number(getComputedStyle(r.querySelector('.tag')).fontWeight)],
}))"""


def stamp(hours_old: float) -> str:
    return (NOW - timedelta(hours=hours_old)).strftime("%Y-%m-%dT%H:%M:%SZ")


def serve(net: Net, companies: list[tuple] = COMPANIES) -> None:
    prices = [{"id": cid, "name": name, "color": color, "source": f"https://{cid}.example/", "time": stamp(hours),
               "basis": basis, "prices": [{"grade": g, "fuel": f, "price": p} for g, f, p in grades]}
              for cid, name, color, hours, basis, grades in companies]
    net.data["prices.json"] = {"generated": stamp(1), "companies": prices}
    net.data["stations.json"] = {"generated": stamp(1), "companies": []}


def open_list(page: Page, net: Net, fuel: str = "დიზელი", scheme: str = "light") -> list[dict]:
    serve(net)
    page.emulate_media(color_scheme=scheme)
    page.clock.set_fixed_time(NOW)
    page.goto(net.base)
    page.get_by_text(fuel, exact=True).first.click()
    return lines(page)


def lines(page: Page) -> list[dict]:
    expect(page.locator(ROWS).first).to_be_attached()
    return page.locator(ROWS).evaluate_all(LINES_JS)


def test_the_list_is_the_chosen_fuels_cheapest_first_one_line_per_grade(page: Page, net: Net) -> None:
    # AC-005: cheapest first, an equal price by the company's name; Connect's two diesels on two lines; "cheapest" on
    # both lines with the lowest fresh price (4.85), not on Lukoil's lower but old one; each line's time, the
    # company's own date where it gave it, the old price's note
    got = open_list(page, net)
    assert [(g["name"], g["grade"], g["price"], g["cheap"], g["stale"]) for g in got] == DIESEL, got
    assert [g["tag"] for g in got] == [None, "იაფი", "იაფი", None, None], got
    assert all(g["discs"] == 1 and g["time"].startswith(f"შემოწმდა {READ_AT}") for g in got[1:]), got
    assert "შესაძლოა მოძველებულია" in got[0]["time"] and "შესაძლოა მოძველებულია" not in got[1]["time"], got
    assert "კომპანიის თარიღი" in got[3]["time"] and "კომპანიის თარიღი" not in got[1]["time"], got
    expect(page.locator("#price-list")).not_to_contain_text("Rompetrol")  # no diesel price: not in the list
    page.get_by_text("რეგულარი", exact=True).first.click()  # the list follows the fuel
    expect(page.locator(ROWS)).to_have_count(2)
    got = lines(page)
    assert [(g["name"], g["price"], g["tag"]) for g in got] == [("Rompetrol", "3.05 ₾", "იაფი"),
                                                                ("SOCAR", "3.10 ₾", None)], got


@pytest.mark.parametrize(("scheme", "ground"), [("light", "rgb(255, 243, 196)"), ("dark", "rgb(58, 48, 24)")])
def test_the_cheapest_lines_ground_and_its_yellow_word(page: Page, net: Net, scheme: str, ground: str) -> None:
    # REQ-006: the cheapest line on #FFF3C4 by day, #3A3018 at night; "cheapest" is a word in #111111 on the yellow,
    # in bold — not only a colour; every line a finger's size, the others on the surface colour
    got = open_list(page, net, scheme=scheme)
    surface = "rgb(255, 255, 255)" if scheme == "light" else "rgb(44, 44, 46)"
    assert [g["ground"] for g in got] == [surface, ground, ground, surface, surface], got
    for g in got:
        assert g["height"] >= 44, g
        if g["cheap"]:
            assert g["tagColours"][:2] == ["rgb(255, 197, 41)", "rgb(17, 17, 17)"] and g["tagColours"][2] >= 700, g


def test_each_line_has_its_companys_circle(page: Page, net: Net) -> None:
    # AC-001's list: the company's 40 px circle, its mark from our list
    open_list(page, net)
    logos = dict(page.evaluate("() => import('./js/logos.js').then((m) => m.LOGOS.map((l) => [l.id, l.file]))"))
    page.wait_for_function(DRAWN, arg="#price-list img")
    discs = page.evaluate(DISCS_JS, "#price-list .disc")
    assert [d["id"] for d in discs] == ["lukoil", "connect", "socar", "wissol", "connect"], discs
    for d in discs:
        assert_icon(d, LIST_DISC)
        assert_mark(d, logos[d["id"]], LIST_DISC)


def test_in_english_the_word_is_cheapest_and_the_time_says_checked(page: Page, net: Net) -> None:
    open_list(page, net)
    page.get_by_role("button", name="ENG").click()
    expect(page.locator("#price-list .tag")).to_have_text(["Cheapest", "Cheapest"])
    expect(page.locator(ROWS).nth(1).locator(".time")).to_have_text(f"Checked {READ_AT}")
    expect(page.locator(ROWS).nth(3).locator(".time")).to_contain_text("the company's date")


def test_the_messages_stand_in_the_lists_place(page: Page, net: Net) -> None:
    # REQ-005: no price for the fuel, every company off — the message is where the list would be, under its title
    open_list(page, net)
    page.get_by_text("ბუნებრივი აირი", exact=True).first.click()
    expect(page.locator(ROWS)).to_have_count(0)
    status = page.locator(".prices #status")
    expect(status).to_have_text("ამ საწვავის ფასი არ მოიძებნა.")
    page.get_by_text("დიზელი", exact=True).first.click()
    for badge in page.locator("#companies .badge").all():
        badge.click()
    expect(page.locator(ROWS)).to_have_count(0)
    expect(status).to_have_text("ჩართე ერთი კომპანია მაინც.")
    title, message = page.locator("#prices-title").bounding_box(), status.bounding_box()
    assert title and message and message["y"] >= title["y"] + title["height"], (title, message)


def test_the_cheapest_rule_counts_only_fresh_prices(page: Page, net: Net) -> None:
    # REQ-005: the lowest fresh price; with no fresh one, no line is marked
    page.goto(net.base)
    got = page.evaluate("""async () => {
      const { lowestFresh } = await import('./js/logic.js');
      const r = (price, stale) => ({ price, stale });
      return [lowestFresh([r(4.5, true), r(4.85, false), r(4.85, false), r(5, false)]), lowestFresh([r(4.5, true)]),
              lowestFresh([])];
    }""")
    assert got == [4.85, None, None]
