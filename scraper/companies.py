"""The companies the price reader reads — only those that pass SPEC-0001 §3's check (docs/domain/fuel-price-sources.md)."""

from __future__ import annotations

from scraper import socar
from scraper.core import Company

COMPANIES = [
    Company(id="socar", name="SOCAR", color="#e41e30", url=socar.URL, parse=socar.parse),
]
