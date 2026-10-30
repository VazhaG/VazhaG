"""Fixtures: the site served from a local port, one browser per run, a phone-sized page per test."""

from __future__ import annotations

import functools
import http.server
import threading
from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

from support import PHONE, SITE, Net


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # keep the test output clean
        pass


@pytest.fixture(scope="session")
def site_url() -> Iterator[str]:
    handler = functools.partial(QuietHandler, directory=str(SITE))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def net(site_url: str) -> Net:
    return Net(site_url)


@pytest.fixture
def page(browser: Browser, net: Net) -> Iterator[Page]:
    context = browser.new_context(viewport=PHONE, locale="ka-GE")
    context.route("**/*", net.handle)
    pg = context.new_page()
    yield pg
    context.close()
