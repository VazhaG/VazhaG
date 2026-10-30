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
    requests: list[str] = field(default_factory=list)
    outside: list[str] = field(default_factory=list)  # requests that would have left the machine

    def handle(self, route: Route) -> None:
        url = route.request.url
        self.requests.append(url)
        if url.startswith(TILE_HOST):
            route.fulfill(status=200, content_type="image/png", body=BLANK_PNG)
        elif url.startswith(self.base):
            path = url[len(self.base):].split("?", 1)[0]
            if path.startswith("data/"):
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
