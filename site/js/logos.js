// SPEC-0004 REQ-003: the logos the page may show — our own files in site/logos/, each the very bytes recorded with its
// source, date and SHA-256 in docs/domain/fuel-price-sources.md (a test compares them). A company has a logo only when
// its code is exactly one of these; the picture's address comes from this list, never from the data.
// One line per company: removing a logo (REQ-004) takes its file and its one line together.
export const LOGOS = Object.freeze([
  Object.freeze({ id: 'socar', file: 'logos/socar.svg', size: [1180, 360], ground: '#111111' }),
  Object.freeze({ id: 'rompetrol', file: 'logos/rompetrol.png', size: [113, 31], ground: '#ffffff' }),
  Object.freeze({ id: 'lukoil', file: 'logos/lukoil.png', size: [1024, 1024], ground: '#ffffff' }),
  Object.freeze({ id: 'wissol', file: 'logos/wissol.svg', size: [56, 56], ground: '#ffffff' }),
  Object.freeze({ id: 'connect', file: 'logos/connect.png', size: [512, 512], ground: '#111111' }),
]);

// A Map, not an object: a code such as "__proto__" or "constructor" finds nothing here.
const BY_ID = new Map(LOGOS.map((logo) => [logo.id, logo]));

export function logoOf(id) {
  return typeof id === 'string' ? BY_ID.get(id) ?? null : null;
}
