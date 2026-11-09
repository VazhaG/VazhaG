// SPEC-0006 REQ-007, ADR-0013 §1: the map's ground — OpenFreeMap's vector map, "liberty" by day and "dark" at night,
// drawn by MapLibre GL JS inside Leaflet (the @maplibre/maplibre-gl-leaflet bridge), its labels in the site's language.
// js/app.js starts it once the list and the icons are drawn, so nothing on the page waits for it.

const STYLE_BASE = 'https://tiles.openfreemap.org/styles/';
const STYLES = { light: 'liberty', dark: 'dark' };
const here = (path) => new URL(path, import.meta.url).href;
const LIBRARY = here('../vendor/maplibre/maplibre-gl.mjs');
const WORKER = here('../vendor/maplibre/maplibre-gl-worker.mjs');
const LIBRARY_CSS = here('../vendor/maplibre/maplibre-gl.css');
const BRIDGE = here('../vendor/maplibre-gl-leaflet/leaflet-maplibre-gl.js');
// a label in the site's language: the Georgian name, else the place's own; in English, a Latin name (REQ-007)
const LABELS = {
  ka: ['coalesce', ['get', 'name:ka'], ['get', 'name']],
  en: ['coalesce', ['get', 'name:latin'], ['get', 'name:en']],
};

const state = { kind: 'loading', layer: null, styles: {}, shown: null, turn: 0 };

// what the map's ground is — 'loading' until MapLibre's first `load`, then 'vector' — and MapLibre's own map; the
// tests read MapLibre's style through it (tests/support.py: GROUND_JS)
export function ground() {
  return { kind: state.kind, map: state.layer?.getMaplibreMap() ?? null };
}

function look() {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
}

function language() {
  return document.documentElement.lang === 'en' ? 'en' : 'ka';
}

function hasWebGL2() {
  try {
    const gl = document.createElement('canvas').getContext('webgl2');
    gl?.getExtension('WEBGL_lose_context')?.loseContext(); // the probe gives its drawing context back
    return Boolean(gl);
  } catch {
    return false;
  }
}

// a layer whose text is a name gets the language's name; a road's number and anything else stay as they are
function localized(style, lang) {
  const layers = style.layers.map((layer) => {
    const text = layer.layout?.['text-field'];
    if (text === undefined || !JSON.stringify(text).includes('name')) return layer;
    return { ...layer, layout: { ...layer.layout, 'text-field': LABELS[lang] } };
  });
  return { ...style, layers };
}

async function fetchStyle(name) {
  const response = await fetch(STYLE_BASE + name);
  if (!response.ok) throw new Error(`style ${name}: ${response.status}`);
  const style = await response.json();
  if (!Array.isArray(style?.layers)) throw new Error(`style ${name}: no layers`);
  return style;
}

function script(src) {
  return new Promise((resolve, reject) => {
    const el = document.createElement('script');
    el.src = src;
    el.onload = resolve;
    el.onerror = () => reject(new Error(`script ${src}`));
    document.head.append(el);
  });
}

function stylesheet(href) {
  return new Promise((resolve) => {
    const el = document.createElement('link');
    el.rel = 'stylesheet';
    el.href = href;
    el.onload = resolve;
    el.onerror = resolve; // MapLibre's own controls are not used: without its stylesheet the map is drawn all the same
    document.head.append(el);
  });
}

// MapLibre 6 is an ES module only; the bridge is a plain script that reads it by its global name (ADR-0013 §1)
async function loadLibrary() {
  const maplibregl = await import(LIBRARY);
  window.maplibregl = maplibregl;
  maplibregl.setWorkerUrl(WORKER); // its worker file is ours, beside it (the CSP's worker-src 'self')
  await Promise.all([script(BRIDGE), stylesheet(LIBRARY_CSS)]);
}

// the look or the language changed: the look's style — asked once, then kept — with the language's labels
async function restyle() {
  const gl = state.layer?.getMaplibreMap();
  const wanted = `${look()} ${language()}`;
  if (!gl || wanted === state.shown) return;
  const turn = ++state.turn;
  let style = state.styles[look()];
  if (!style) {
    try {
      style = await fetchStyle(STYLES[look()]);
    } catch (error) {
      console.warn('the map style did not load', error);
      return;
    }
    state.styles[look()] = style;
    if (turn !== state.turn) return; // a later change is under way
  }
  state.shown = `${look()} ${language()}`;
  gl.setStyle(localized(style, language()));
}

export async function startGround(map) {
  if (!hasWebGL2()) return;
  const first = look();
  try {
    const [style] = await Promise.all([fetchStyle(STYLES[first]), loadLibrary()]);
    state.styles[first] = style;
    state.shown = `${first} ${language()}`;
    state.layer = L.maplibreGL({ style: localized(style, language()) }).addTo(map);
  } catch (error) {
    console.warn('the vector map did not start', error);
    return;
  }
  state.layer.getMaplibreMap().once('load', () => {
    state.kind = 'vector';
    map.getContainer().dataset.ground = 'vector';
  });
  new MutationObserver(restyle).observe(document.documentElement, { attributeFilter: ['data-theme', 'lang'] });
  restyle(); // the look or the language may have changed while the library was on its way
}
