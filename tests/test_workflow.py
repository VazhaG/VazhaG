"""T9 — the scheduled run: every 3 hours (AC-005), pinned actions, and when it commits the data files.

SPEC-0001: REQ-006, REQ-007, AC-005; ADR-0012.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path

from scraper.changed import KEEPALIVE, changed, comparable
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


def test_the_run_reads_publishes_and_turns_red_on_a_bad_reading() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python -m scraper\n" in text
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
