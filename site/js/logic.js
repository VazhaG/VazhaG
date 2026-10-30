// The rules the page applies to the data — plain functions, so the tests call them directly (SPEC-0001).

export const STALE_MS = 48 * 3600 * 1000; // REQ-006: 48 hours and more — greyed out
export const HIDDEN_MS = 7 * 24 * 3600 * 1000; // REQ-006: 7 days and more — not shown

// AC-002: a station is drawn only with a numeric place inside this box around Georgia.
export const LAT_RANGE = [41.0, 43.7];
export const LNG_RANGE = [39.9, 46.8];

const COLOR_RE = /^#[0-9a-f]{6}$/i;
const NEUTRAL = '#94a3b8';

export function freshness(timeIso, now) {
  const time = typeof timeIso === 'string' ? Date.parse(timeIso) : NaN;
  if (Number.isNaN(time)) return 'hidden';
  const age = now - time;
  if (age >= HIDDEN_MS) return 'hidden';
  return age >= STALE_MS ? 'stale' : 'fresh';
}

export function safeColor(color) {
  return typeof color === 'string' && COLOR_RE.test(color) ? color : NEUTRAL;
}

// Every shown price of one fuel, cheapest first. A company needs a source and a time (REQ-006).
export function priceRows(data, fuel, now) {
  const rows = [];
  for (const c of data?.companies ?? []) {
    if (typeof c?.source !== 'string' || !c.source) continue;
    const state = freshness(c.time, now);
    if (state === 'hidden') continue;
    for (const p of c.prices ?? []) {
      if (p?.fuel !== fuel || typeof p.price !== 'number' || !Number.isFinite(p.price)) continue;
      rows.push({
        company: String(c.name ?? ''),
        color: safeColor(c.color),
        grade: String(p.grade ?? ''),
        price: p.price,
        time: c.time,
        stale: state === 'stale',
      });
    }
  }
  rows.sort((a, b) => a.price - b.price || a.company.localeCompare(b.company));
  return rows;
}

export function placed(lat, lng) {
  return typeof lat === 'number' && typeof lng === 'number'
    && lat >= LAT_RANGE[0] && lat <= LAT_RANGE[1] && lng >= LNG_RANGE[0] && lng <= LNG_RANGE[1];
}

// The stations that sell this fuel and have a known place in Georgia (REQ-001, REQ-002, AC-002).
// A company needs a source, like its prices (REQ-006).
export function stationsFor(data, fuel) {
  const out = [];
  for (const c of data?.companies ?? []) {
    if (typeof c?.source !== 'string' || !c.source) continue;
    for (const s of c.stations ?? []) {
      if (!placed(s?.lat, s?.lng) || !Array.isArray(s.fuels) || !s.fuels.includes(fuel)) continue;
      out.push({
        companyId: String(c.id ?? ''),
        company: String(c.name ?? ''),
        color: safeColor(c.color),
        name: String(s.name ?? ''),
        address: String(s.address ?? ''),
        lat: s.lat,
        lng: s.lng,
      });
    }
  }
  return out;
}
