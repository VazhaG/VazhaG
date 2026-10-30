"""The companies the price reader reads — those that pass SPEC-0001 §3's check, plus Wissol by the owner's decision
(docs/domain/fuel-price-sources.md). The colours tell the companies apart on the map; they are not the brands' own.
"""

from __future__ import annotations

from scraper import lukoil, rompetrol, socar, wissol
from scraper.core import Company

# The owner's decision, 2026-10-30 (SPEC-0001 §3, §7). False stops reading Wissol and removes its prices.
WISSOL_ENABLED = True

COMPANIES = [
    Company(id="socar", name="SOCAR", color="#e41e30", url=socar.URL, parse=socar.parse,
            stations_url=socar.STATIONS_URL, parse_stations=socar.parse_stations),
    Company(id="rompetrol", name="Rompetrol", color="#f39200", url=rompetrol.URL, parse=rompetrol.parse,
            stations_url=rompetrol.STATIONS_URL, parse_stations=rompetrol.parse_stations),
    Company(id="lukoil", name="Lukoil", color="#8a1538", url=lukoil.URL, parse=lukoil.parse,
            stations_url=lukoil.STATIONS_URL, parse_stations=lukoil.parse_stations),
    Company(id="wissol", name="Wissol", color="#00843d", url=wissol.URL, parse=wissol.parse, enabled=WISSOL_ENABLED,
            stations_url=wissol.STATIONS_URL, parse_stations=wissol.parse_stations),
]
