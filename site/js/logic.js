// The rules the page applies to the data — plain functions, so the tests call them directly (SPEC-0001).

export const STALE_MS = 48 * 3600 * 1000; // REQ-006: 48 hours and more — greyed out
export const HIDDEN_MS = 7 * 24 * 3600 * 1000; // REQ-006: 7 days and more — not shown

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
