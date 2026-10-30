"""The reader's download — SPEC-0001 REQ-007: one source that answers slowly, endlessly or cut short fails alone.

A local server stands in for the companies' sites; nothing here reaches the internet.
"""

from __future__ import annotations

import http.client
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scraper import core
from scraper.core import ParseError, fetch

PAGE = "<p>დიზელი 4.95 ₾</p>"
LATIN = "<p>Diesel · 4.95 - café</p>"  # every character in ISO-8859-1
STOP = threading.Event()


class Source(BaseHTTPRequestHandler):
    """HTTP/1.0: an answer without a length ends when the connection closes."""

    def answer(self, length: int | None, content_type: str = "text/html") -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/page":
            body = PAGE.encode("utf-8")
            self.answer(len(body), "text/html; charset=utf-8")
            self.wfile.write(body)
        elif self.path == "/latin":  # not the UTF-8 the reader falls back to
            body = LATIN.encode("iso-8859-1")
            self.answer(len(body), "text/html; charset=iso-8859-1")
            self.wfile.write(body)
        elif self.path == "/drip":  # 30 bytes, one every 0.1 s — each well inside the socket timeout
            self.answer(30)
            for _ in range(30):
                if STOP.wait(0.1):
                    return
                self.wfile.write(b"x")
                self.wfile.flush()
        elif self.path == "/endless":
            self.answer(None)
            try:
                while not STOP.is_set():
                    self.wfile.write(b"x" * 5000)
            except (BrokenPipeError, ConnectionResetError):  # the reader stopped taking it
                pass
        elif self.path == "/cut":
            self.answer(1000)
            self.wfile.write(b"x" * 10)  # and the connection closes
        elif self.path == "/odd-length":  # "²" is a digit to str.isdigit(), not to int()
            self.send_response(200)
            self.send_header("Content-Length", "²")
            self.end_headers()
            self.wfile.write(PAGE.encode("utf-8"))

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def site() -> Iterator[str]:
    STOP.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Source)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    STOP.set()
    server.shutdown()
    server.server_close()


def test_a_page_is_read_in_its_own_charset(site: str) -> None:
    assert fetch(f"{site}/page") == PAGE
    assert fetch(f"{site}/latin") == LATIN


def test_a_source_that_drips_fails_at_the_deadline(site: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # The socket timeout counts each read on its own: a page sent byte by byte would hold the whole run
    monkeypatch.setattr(core, "DEADLINE_S", 0.5)
    start = time.perf_counter()
    with pytest.raises(TimeoutError):
        fetch(f"{site}/drip")
    assert time.perf_counter() - start < 2


def test_a_source_that_never_ends_fails_at_the_size_limit(site: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # An unbounded read would only end at the deadline, and its thread would go on filling memory after it
    monkeypatch.setattr(core, "MAX_BYTES", 1000)
    monkeypatch.setattr(core, "DEADLINE_S", 2.0)
    with pytest.raises(ParseError, match="larger than"):
        fetch(f"{site}/endless")


def test_a_page_cut_short_is_not_read_as_whole(site: str) -> None:
    with pytest.raises(http.client.IncompleteRead):
        fetch(f"{site}/cut")


def test_a_length_that_is_not_a_plain_number_is_ignored(site: str) -> None:
    # as http.client itself ignores it: the page is read to its end
    assert fetch(f"{site}/odd-length") == PAGE
