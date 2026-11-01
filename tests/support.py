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

    def handle(self, route: Route) -> None:
        url = route.request.url
        self.requests.append(url)
        if route.request.post_data:
            self.bodies.append(route.request.post_data)
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
    """Serve a logo list without any company: every badge is a name on its colour, as for a company without a logo."""
    net.files["js/logos.js"] = (200, "text/javascript", logos_without(*LOGO_IDS))
