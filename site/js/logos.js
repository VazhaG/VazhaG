// SPEC-0004 REQ-003: the logos the page may show — our own files in site/logos/, each the very bytes recorded with its
// source, date and SHA-256 in docs/domain/fuel-price-sources.md (a test compares them). A company has a logo only when
// its code is exactly one of these; the picture's address comes from this list, never from the data.
// size: the file's own width and height. mark: the part of the file that is recognised small, for the map (REQ-002) —
// x, y, width, height in the file's pixels (SOCAR's flame, Rompetrol's flower, Lukoil's red square, Wissol's and
// Connect's whole sign; measured 2026-11-01 — a hypothesis the owner sees in a picture).
// One line per company: removing a logo (REQ-004) takes its file and its one line together.
export const LOGOS = Object.freeze([
  Object.freeze({ id: 'socar', file: 'logos/socar.svg', size: [1180, 360], ground: '#111111', mark: [0, 0, 222, 360] }),
  Object.freeze({ id: 'rompetrol', file: 'logos/rompetrol.png', size: [113, 31], ground: '#ffffff', mark: [0, 0, 40, 27] }),
  Object.freeze({ id: 'lukoil', file: 'logos/lukoil.png', size: [1024, 1024], ground: '#ffffff', mark: [198, 96, 628, 630] }),
  Object.freeze({ id: 'wissol', file: 'logos/wissol.svg', size: [56, 56], ground: '#ffffff', mark: [0, 0, 56, 56] }),
  Object.freeze({ id: 'connect', file: 'logos/connect.png', size: [512, 512], ground: '#111111', mark: [0, 16, 505, 474] }),
]);

// A Map, not an object: a code such as "__proto__" or "constructor" finds nothing here.
const BY_ID = new Map(LOGOS.map((logo) => [logo.id, logo]));

export function logoOf(id) {
  return typeof id === 'string' ? BY_ID.get(id) ?? null : null;
}
