"""Shared test helpers: where the site lives and a stand-in for the network.

The tests never reach the internet: map tiles get a blank picture, the data files get what the test chooses,
and every other request outside the local server is refused and recorded (SPEC-0001 AC-010).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import Route

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
LOGOS_JS = SITE / "js" / "logos.js"
LOGO_IDS = ("socar", "rompetrol", "lukoil", "wissol", "connect")  # the companies with a logo (SPEC-0004)
# every picture the selector finds has its address and is drawn — a logo gets its address once its file has arrived
DRAWN = "(sel) => [...document.querySelectorAll(sel)].every((i) => i.getAttribute('src') && i.naturalWidth > 0)"
FRAME_GREY = "rgb(142, 142, 147)"  # #8E8E93 — a company circle's frame, in both looks (SPEC-0005 REQ-001)
# where a station's mark stands on the map: a pin's tip from the city view on (SPEC-0005 REQ-007 — the lowest point of
# its turned square), else the middle of its dot
POINT_JS = """(m) => {
  const pin = m.querySelector('.pin'), r = (pin || m).getBoundingClientRect();
  return [r.left + r.width / 2, pin ? r.bottom : r.top + r.height / 2];
}"""
# SPEC-0005 REQ-001: every company circle the selector finds, measured as drawn — its size, fill, frame and what is
# behind it; a logo's picture and the part of it that shows (its mark, cut by clip-path from the file's own pixels);
# a letter circle's fill and ink. The frame is the circle's border or, drawn inside it, its outline.
DISCS_JS = """async (sel) => {
  const { LOGOS } = await import('./js/logos.js');
  const byId = new Map(LOGOS.map((l) => [l.id, l]));
  const behind = (el) => {
    for (el = el.parentElement; el; el = el.parentElement) {
      const c = getComputedStyle(el).backgroundColor.match(/[\\d.]+/g).map(Number);
      if (c.length < 4 || c[3] > 0) return 'rgb(' + c.slice(0, 3).join(', ') + ')';
    }
    return 'rgb(255, 255, 255)';
  };
  const px = (v, total) => (v.endsWith('%') ? (parseFloat(v) / 100) * total : parseFloat(v));
  return [...document.querySelectorAll(sel)].map((d) => {
    const r = d.getBoundingClientRect(), s = getComputedStyle(d);
    const border = parseFloat(s.borderTopWidth), outline = s.outlineStyle === 'none' ? 0 : parseFloat(s.outlineWidth);
    const id = d.closest('[data-company]')?.dataset.company;  // the badge, the line or the marker it is drawn in
    const out = {
      id, size: [r.width, r.height], ground: s.backgroundColor, round: s.borderRadius,
      opacity: Number(s.opacity), behind: behind(d), imgs: d.querySelectorAll('img').length, text: d.textContent,
      frame: border > 0 ? [s.borderTopStyle, border, s.borderTopColor, true]
        : [s.outlineStyle, outline, s.outlineColor, parseFloat(s.outlineOffset) <= -outline + 0.01],
    };
    const letter = d.querySelector('.letter');
    if (letter) {
      const ls = getComputedStyle(letter), lr = letter.getBoundingClientRect();
      out.letter = { fill: ls.backgroundColor, ink: ls.color, size: [lr.width, lr.height], round: ls.borderRadius,
                     font: parseFloat(ls.fontSize), filter: ls.filter, opacity: Number(ls.opacity) };
    }
    const img = d.querySelector('img'), logo = byId.get(id);
    if (img && logo) {
      const ir = img.getBoundingClientRect(), k = ir.width / logo.size[0], [x, y, w, h] = logo.mark;
      const at = [ir.left + x * k, ir.top + y * k, w * k, h * k];
      const v = getComputedStyle(img).clipPath.match(/-?[\\d.]+(?:px|%)?/g) || [];
      // inset() is written like a margin: one, two, three or four values — top, right, bottom, left
      const [t, rt, b, lt] = [v[0], v[1] ?? v[0], v[2] ?? v[0], v[3] ?? v[1] ?? v[0]];
      const shown = v.length ? [ir.left + px(lt, ir.width), ir.top + px(t, ir.height),
                                ir.width - px(lt, ir.width) - px(rt, ir.width),
                                ir.height - px(t, ir.height) - px(b, ir.height)] : null;
      Object.assign(out, {
        src: img.getAttribute('src'), alt: img.getAttribute('alt'), loaded: img.complete && img.naturalWidth > 0,
        filter: getComputedStyle(img).filter, markOpacity: Number(getComputedStyle(img).opacity),
        clip: getComputedStyle(img).clipPath, at, shown, long: Math.max(w * k, h * k),
        off: [at[0] + at[2] / 2 - (r.left + r.width / 2), at[1] + at[3] / 2 - (r.top + r.height / 2)],
      });
    }
    return out;
  });
}"""
TILE_HOST = "https://tile.openstreetmap.org/"
BLANK_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)
PHONE = {"width": 375, "height": 812}


@dataclass
class Net:
    """What the page asked for, and what the test serves in place of the real data files."""

    base: str
    data: dict[str, object] = field(default_factory=dict)  # "prices.json" -> JSON content; missing -> 404
    real_data: bool = False  # serve site/data/ as it is, through the local server
    requests: list[str] = field(default_factory=list)
    bodies: list[str] = field(default_factory=list)  # what the page sent, if anything
    outside: list[str] = field(default_factory=list)  # requests that would have left the machine
    files: dict[str, tuple[int, str, str | bytes]] = field(default_factory=dict)  # a site file as the test serves it
    held: set[str] = field(default_factory=set)  # site files left unanswered, as on a stalled network
    pending: dict[str, Route] = field(default_factory=dict)  # a held file's open request — a test may answer it late

    def handle(self, route: Route) -> None:
        url = route.request.url
        self.requests.append(url)
        if route.request.post_data:
            self.bodies.append(route.request.post_data)
        path = url[len(self.base):].split("?", 1)[0] if url.startswith(self.base) else None
        if path in self.held:
            self.pending[path] = route  # unanswered until the test answers it, or the page closes
            return
        if url.startswith(TILE_HOST):
            route.fulfill(status=200, content_type="image/png", body=BLANK_PNG)
        elif url.startswith(self.base):
            path = url[len(self.base):].split("?", 1)[0]
            if path in self.files:
                status, content_type, body = self.files[path]
                route.fulfill(status=status, content_type=content_type, body=body)
            elif path.startswith("data/") and not self.real_data:
                name = path[len("data/"):]
                if name in self.data:
                    body = json.dumps(self.data[name], ensure_ascii=False)
                    route.fulfill(status=200, content_type="application/json", body=body)
                else:
                    route.fulfill(status=404, body="")
            else:
                route.continue_()
        else:
            self.outside.append(url)
            route.abort()


def logos_without(*ids: str) -> str:
    """The page's logo list (site/js/logos.js) with these companies' lines taken out — as after a removal
    (SPEC-0004 REQ-004): one line per company, so each named company must take exactly one line with it."""
    lines = LOGOS_JS.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [line for line in lines if not any(f"id: '{cid}'" in line for cid in ids)]
    assert len(lines) - len(kept) == len(ids), ids
    return "".join(kept)


def no_logos(net: Net) -> None:
    """Serve a logo list without any company: every company is its colour and first letter, as one without a logo."""
    net.files["js/logos.js"] = (200, "text/javascript", logos_without(*LOGO_IDS))


def rgb(text: str) -> tuple[int, ...]:
    """'rgb(1, 2, 3)' or 'rgba(1, 2, 3, 0.5)' -> (1, 2, 3)."""
    return tuple(int(float(v)) for v in text[text.index("(") + 1:text.index(")")].split(",")[:3])


def ratio(a: tuple[int, ...], b: tuple[int, ...]) -> float:
    """WCAG contrast ratio of two colours."""
    def lum(c: tuple[int, ...]) -> float:
        parts = [v / 255 for v in c]
        parts = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in parts]
        return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]

    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# SPEC-0005 REQ-001, AC-001 — a company circle as DISCS_JS measured it, wherever it is drawn
def assert_disc(d: dict, size: float) -> None:
    """One circle of this size, black, round, in its frame (3 : 1 on what is behind it)."""
    assert all(abs(v - size) <= 0.5 for v in d["size"]) and d["round"] == "50%", d
    assert d["ground"] == "rgb(0, 0, 0)" and d["opacity"] == 1, d
    style, width, color, inside = d["frame"]
    assert style == "solid" and width >= 1.5 and color == FRAME_GREY and inside, d
    assert ratio(rgb(color), rgb(d["behind"])) >= 3, d


def assert_mark(d: dict, file: str, size: float) -> None:
    """The logo's mark from our list — drawn, its longer side 60 % of the circle (±2 px), in the circle's middle, and
    only the mark shows through the cut."""
    assert d["imgs"] == 1 and d["text"] == "" and "letter" not in d, d
    assert (d["src"], d["alt"], d["loaded"], d["filter"], d["markOpacity"]) == (file, "", True, "none", 1), d
    assert abs(d["long"] - 0.6 * size) <= 2 and max(abs(v) for v in d["off"]) <= 0.5, d
    assert d["clip"].startswith("inset(") and d["shown"], d
    assert all(abs(a - b) <= 0.6 for a, b in zip(d["shown"], d["at"], strict=True)), d


def assert_letter(d: dict, size: float, letter: str, fill: str) -> None:
    """A company without a logo — the same circle, all of it its colour, with its first letter."""
    assert d["imgs"] == 0 and d["text"] == letter, d
    got = d["letter"]
    assert got["fill"] == fill and got["round"] == "50%" and all(abs(v - size) <= 0.5 for v in got["size"]), d
    assert ratio(rgb(got["ink"]), rgb(got["fill"])) >= 4.5 and got["font"] >= 0.35 * size, d
