"""PLAN-0006 T5 — the libraries the site carries are exactly the published files, each with its licence.

ADR-0013 §1 and its "how we confirm": every library in `site/vendor/` has a LICENSE and a source record
(`SOURCE.txt`: the package and its exact version, the registry address and integrity, the dates, and a SHA-256 for
every file in the folder); the test compares each file with that record. The version must have been at least two
weeks old on the day it was added — new versions are where a mistake or a malicious change usually shows up first.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re

import pytest

from support import SITE

VENDOR = SITE / "vendor"
LIBRARIES = {  # folder → the exact package and version ADR-0013 names (Leaflet: ADR-0012, restated there)
    "leaflet": "leaflet@1.9.4",
    "maplibre": "maplibre-gl@6.16.0",
    "maplibre-gl-leaflet": "@maplibre/maplibre-gl-leaflet@0.1.4",
}
LICENCES = {"LICENSE", "LICENSE.txt"}
MIN_AGE = dt.timedelta(days=14)
FIELD_RE = re.compile(r"^(Package|Source|Integrity|Published|Added): (\S+)$", re.MULTILINE)
SUM_RE = re.compile(r"^([0-9a-f]{64})  (\S+)$", re.MULTILINE)  # the `sha256sum` line: digest, two spaces, file
INTEGRITY_RE = re.compile(r"sha512-[A-Za-z0-9+/]{86}==")


def record(folder: str) -> tuple[dict[str, str], dict[str, str]]:
    """The folder's SOURCE.txt: its fields, and its SHA-256 lines as {file: digest}."""
    text = (VENDOR / folder / "SOURCE.txt").read_text(encoding="utf-8")
    return dict(FIELD_RE.findall(text)), {name: digest for digest, name in SUM_RE.findall(text)}


def files_in(folder: str) -> list[str]:
    return sorted(p.relative_to(VENDOR / folder).as_posix() for p in (VENDOR / folder).rglob("*") if p.is_file())


def test_the_site_carries_exactly_the_pinned_libraries() -> None:
    assert sorted(p.name for p in VENDOR.iterdir()) == sorted(LIBRARIES)


@pytest.mark.parametrize("folder", sorted(LIBRARIES))
def test_each_librarys_record_names_its_exact_version_and_where_it_came_from(folder: str) -> None:
    fields, _ = record(folder)
    package = LIBRARIES[folder]
    name, version = package.rsplit("@", 1)
    assert fields.get("Package") == package
    assert fields.get("Source") == f"https://registry.npmjs.org/{name}/-/{name.split('/')[-1]}-{version}.tgz"
    assert INTEGRITY_RE.fullmatch(fields.get("Integrity", "")), fields.get("Integrity")


@pytest.mark.parametrize("folder", sorted(LIBRARIES))
def test_every_file_of_a_library_is_the_one_its_record_names(folder: str) -> None:
    _, sums = record(folder)
    # nothing unlisted in the folder, nothing listed and missing
    assert sorted(sums) == [f for f in files_in(folder) if f != "SOURCE.txt"]
    for name, digest in sums.items():
        assert hashlib.sha256((VENDOR / folder / name).read_bytes()).hexdigest() == digest, name


@pytest.mark.parametrize("folder", sorted(LIBRARIES))
def test_every_library_carries_its_licence(folder: str) -> None:
    _, sums = record(folder)
    licences = [f for f in files_in(folder) if f in LICENCES]
    assert licences, f"{folder}: no LICENSE"
    for f in licences:
        assert f in sums, f"{folder}/{f} is not pinned in SOURCE.txt"
        assert "copyright" in (VENDOR / folder / f).read_text(encoding="utf-8").lower()


@pytest.mark.parametrize("folder", sorted(LIBRARIES))
def test_every_version_was_two_weeks_old_when_it_was_added(folder: str) -> None:
    fields, _ = record(folder)
    published = dt.date.fromisoformat(fields["Published"])
    added = dt.date.fromisoformat(fields["Added"])
    assert added - published >= MIN_AGE, f"{folder}: {published} → {added}"
    assert added <= dt.date.today()
