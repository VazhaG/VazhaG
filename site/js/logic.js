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
        fuels: s.fuels.map(String),
        grades: Array.isArray(s.grades) ? s.grades.map(String) : null,
      });
    }
  }
  return out;
}

export const RADII_KM = [5, 10, 20, 50]; // REQ-003: the zone grows until a station is found
const GASES = ['lpg', 'cng'];
const EARTH_KM = 6371.0088;

export function distanceKm(a, b) {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLng = (b.lng - a.lng) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_KM * Math.asin(Math.sqrt(h));
}

// What one station sells of one fuel, cheapest first: its company's shown prices of that fuel, narrowed to the
// station's own grades when its list names them (REQ-003). Prices 7 days old are not shown (REQ-006).
export function stationPrices(company, station, fuel, now) {
  if (!station.fuels.includes(fuel) || typeof company?.source !== 'string' || !company.source) return [];
  const state = freshness(company.time, now);
  if (state === 'hidden') return [];
  let list = (company.prices ?? []).filter(
    (p) => p?.fuel === fuel && typeof p.price === 'number' && Number.isFinite(p.price),
  );
  const named = station.grades ? list.filter((p) => station.grades.includes(String(p.grade))) : [];
  if (named.length) list = named;
  return list
    .map((p) => ({ grade: String(p.grade ?? ''), price: p.price, stale: state === 'stale' }))
    .sort((a, b) => a.price - b.price);
}

// REQ-003: the cheapest station within 5 km, then 10, 20, 50; on an equal price the nearer one.
// { best, radius } — or { reason: 'none' }, or for a gas no station is known to sell, { reason: 'gasUnknown' }.
export function cheapestNearby(pricesData, stationsData, fuel, here, now) {
  const priced = new Map();
  for (const c of pricesData?.companies ?? []) {
    if (c?.id != null) priced.set(String(c.id), c);
  }
  const stations = stationsFor(stationsData, fuel);
  if (!stations.length && GASES.includes(fuel)) return { reason: 'gasUnknown' };
  const candidates = [];
  for (const s of stations) {
    const company = priced.get(s.companyId);
    const [cheapest] = company ? stationPrices(company, s, fuel, now) : [];
    if (cheapest) candidates.push({ ...s, ...cheapest, distanceKm: distanceKm(here, s) });
  }
  for (const radius of RADII_KM) {
    const near = candidates.filter((c) => c.distanceKm <= radius);
    if (near.length) {
      near.sort((a, b) => a.price - b.price || a.distanceKm - b.distanceKm);
      return { best: near[0], radius };
    }
  }
  return { reason: 'none' };
}

// AC-007: the station's own place only — the visitor's is never put into a link (REQ-010).
export function routeLinks(lat, lng) {
  const ll = encodeURIComponent(`${lat},${lng}`);
  return {
    google: `https://www.google.com/maps/dir/?api=1&destination=${ll}`,
    waze: `https://www.waze.com/ul?ll=${ll}&navigate=yes`,
  };
}
