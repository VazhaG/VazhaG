"""T9 — the scheduled run: every 3 hours (AC-005), pinned actions, and when it commits the data files.

SPEC-0001: REQ-006, REQ-007, AC-005; ADR-0012.
"""

from __future__ import annotations

import http.client
import importlib.metadata
import json
import re
import urllib.error
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest

from scraper import published
from scraper.changed import KEEPALIVE, changed, comparable
from scraper.core import ParseError
from scraper.published import TRIES, start
from support import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "prices.yml"
NOW = 1_800_000_000.0


def test_the_schedule_is_at_most_every_3_hours_and_off_the_hour() -> None:
    crons = re.findall(r'cron:\s*"([^"]+)"', WORKFLOW.read_text(encoding="utf-8"))
    assert crons == ["17 */3 * * *"]
    minute, hours = crons[0].split()[:2]
    assert minute != "0"
    assert int(hours.removeprefix("*/")) <= 3


def test_every_action_is_pinned_to_a_commit() -> None:
    uses = re.findall(r"uses:\s*(\S+)", WORKFLOW.read_text(encoding="utf-8"))
    assert len(uses) == 5
    for ref in uses:
        assert re.fullmatch(r"actions/[\w-]+@[0-9a-f]{40}", ref), ref


PUBLISHED = "https://vazhag.github.io/VazhaG/data/"
REPOSITORY_COPY = '{"generated": "2026-10-01T09:00:00Z", "companies": []}'
FRESH = '{"generated": "2026-10-30T09:00:00Z", "companies": []}'


def repository_copy(tmp_path: Path) -> list[Path]:
    paths = [tmp_path / "prices.json", tmp_path / "stations.json"]
    for path in paths:
        path.write_text(REPOSITORY_COPY, encoding="utf-8")
    return paths


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(PUBLISHED, code, "test", None, None)  # type: ignore[arg-type]


def site_answering(answers: dict[str, list[object]]) -> tuple[Callable[[str], str], list[str]]:
    """A stand-in for the published site: each file's answers in order — a text, or a failure to raise."""
    calls: list[str] = []

    def get(url: str) -> str:
        calls.append(url)
        answer = answers[url.removeprefix(PUBLISHED)].pop(0)
        if isinstance(answer, Exception):
            raise answer
        return str(answer)

    return get, calls


def no_wait(seconds: float) -> None:
    pass


def test_the_run_starts_from_the_published_files(tmp_path: Path) -> None:
    paths = repository_copy(tmp_path)
    get, _ = site_answering({"prices.json": [FRESH], "stations.json": [FRESH]})
    start(PUBLISHED, paths, get, no_wait)
    assert [p.read_text(encoding="utf-8") for p in paths] == [FRESH, FRESH]


def test_before_the_first_publication_the_repository_copy_is_the_start(tmp_path: Path) -> None:
    paths = repository_copy(tmp_path)
    get, calls = site_answering({"prices.json": [http_error(404)], "stations.json": [http_error(404)]})
    log = start(PUBLISHED, paths, get, no_wait)
    assert [p.read_text(encoding="utf-8") for p in paths] == [REPOSITORY_COPY, REPOSITORY_COPY]
    assert len(calls) == 2  # "not there" is an answer: it is not asked again
    assert "no published prices.json yet — starting from the repository's" in log


@pytest.mark.parametrize("broken", ["<html><body>Page not found</body></html>", "[]", '{"companies": "x"}'])
def test_a_broken_published_file_does_not_stop_every_run_after_it(tmp_path: Path, broken: str) -> None:
    paths = repository_copy(tmp_path)
    get, _ = site_answering({"prices.json": [broken], "stations.json": [FRESH]})
    log = start(PUBLISHED, paths, get, no_wait)
    assert [p.read_text(encoding="utf-8") for p in paths] == [REPOSITORY_COPY, FRESH]
    assert log[0].startswith("::warning::the published prices.json is not a data file")


def test_a_published_file_too_large_to_take_does_not_stop_every_run_after_it(tmp_path: Path) -> None:
    paths = repository_copy(tmp_path)
    get, calls = site_answering({"prices.json": [ParseError("the answer is larger than 10 MB")],
                                 "stations.json": [FRESH]})
    log = start(PUBLISHED, paths, get, no_wait)
    assert [p.read_text(encoding="utf-8") for p in paths] == [REPOSITORY_COPY, FRESH]
    assert log[0] == ("::warning::the published prices.json could not be taken (the answer is larger than 10 MB) — "
                      "starting from the repository's")
    assert len(calls) == 2  # the same file would be as large again: it is not asked twice


@pytest.mark.parametrize("failure", [http_error(503), urllib.error.URLError("connection refused"),
                                     http.client.IncompleteRead(b'{"generated"')])
def test_any_other_failure_stops_the_run_after_three_tries(tmp_path: Path, failure: Exception) -> None:
    # The repository copy's times can be weeks old (scraper/changed.py): starting from it now would hide prices read
    # hours ago and turn their companies overdue, so the run stops instead and nothing old is published again.
    paths = repository_copy(tmp_path)
    get, calls = site_answering({"prices.json": [failure] * TRIES})
    waits: list[float] = []
    with pytest.raises(type(failure)):
        start(PUBLISHED, paths, get, waits.append)
    assert len(calls) == TRIES == 3
    assert len(waits) == TRIES - 1
    assert paths[0].read_text(encoding="utf-8") == REPOSITORY_COPY


def test_a_failure_that_passes_is_tried_again(tmp_path: Path) -> None:
    paths = repository_copy(tmp_path)
    get, calls = site_answering({"prices.json": [http_error(502), FRESH], "stations.json": [FRESH]})
    start(PUBLISHED, paths, get, no_wait)
    assert [p.read_text(encoding="utf-8") for p in paths] == [FRESH, FRESH]
    assert len(calls) == 3


def test_a_stopped_start_is_a_red_run_with_its_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                       capsys: pytest.CaptureFixture[str]) -> None:
    paths = repository_copy(tmp_path)

    def down(url: str) -> str:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(published, "fetch", down)
    monkeypatch.setattr(published, "WAIT_S", 0)
    assert published.main([PUBLISHED, *map(str, paths)]) == 1
    out = capsys.readouterr().out
    assert out.startswith("::error::") and "connection refused" in out


def test_every_package_the_run_installs_is_pinned() -> None:
    # The run that installs them can commit to the repository and builds the published site: a new release of any of
    # them, bs4's own dependencies included, must not reach it unseen
    lines = [line.strip() for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()]
    pins = dict(line.split("==") for line in lines if line and not line.startswith("#"))
    assert all(re.fullmatch(r"[\w.-]+", name) and re.fullmatch(r"\d+(\.\d+)+", v) for name, v in pins.items()), pins
    wanted = {re.split(r"[ ;<>=!~\[]", r, maxsplit=1)[0].lower().replace("_", "-")
              for name in pins for r in importlib.metadata.requires(name) or [] if "extra ==" not in r}
    assert wanted <= {name.lower().replace("_", "-") for name in pins}


def test_the_run_reads_publishes_and_turns_red_on_a_bad_reading() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    start_at = text.index(f"python -m scraper.published {PUBLISHED} site/data/prices.json site/data/stations.json\n")
    assert start_at < text.index("python -m scraper\n")
    assert "python -m scraper.changed site/data/prices.json site/data/stations.json" in text
    assert "path: site" in text
    assert 'run: test "$STATUS" = "0"' in text
    assert re.search(r"^permissions:\n  contents: read$", text, re.MULTILINE)


def entry(price: float, time: str) -> str:
    return json.dumps({"generated": time, "companies": [{"id": "a", "time": time,
                                                         "prices": [{"grade": "დ", "fuel": "diesel", "price": price}]}]})


def test_only_the_reading_times_changing_is_no_change(tmp_path: Path) -> None:
    path = tmp_path / "prices.json"
    path.write_text(entry(4.90, "2026-10-30T12:00:00Z"), encoding="utf-8")
    old = entry(4.90, "2026-10-30T09:00:00Z")
    assert changed([path], lambda p: old, NOW - 3600, NOW) == (False, "prices and stations as committed")
    assert changed([path], lambda p: entry(4.95, "2026-10-30T09:00:00Z"), NOW - 3600, NOW)[0] is True
    assert changed([path], lambda p: None, NOW - 3600, NOW)[0] is True  # not committed yet
    path.write_text("{}", encoding="utf-8")
    assert changed([path], lambda p: None, NOW - 3600, NOW)[0] is True  # even an empty file, when it is new


def test_thirty_days_without_a_commit_keeps_the_schedule_alive(tmp_path: Path) -> None:
    assert KEEPALIVE == timedelta(days=30)  # well inside GitHub's 60 days (ADR-0012: "monthly")
    path = tmp_path / "prices.json"
    path.write_text(entry(4.90, "t"), encoding="utf-8")
    same = entry(4.90, "t")
    assert changed([path], lambda p: same, NOW - KEEPALIVE.total_seconds() + 60, NOW)[0] is False
    assert changed([path], lambda p: same, NOW - KEEPALIVE.total_seconds(), NOW)[0] is True
    assert changed([path], lambda p: same, None, NOW)[0] is True


def test_comparable_drops_only_the_times() -> None:
    assert comparable(entry(4.9, "a")) == comparable(entry(4.9, "b"))
    assert comparable(entry(4.9, "a")) != comparable(entry(5.0, "a"))
    assert comparable("not json") == "not json"
