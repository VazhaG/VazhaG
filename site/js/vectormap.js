// SPEC-0006 REQ-007, ADR-0013 §1: the map's ground — OpenFreeMap's vector map, "liberty" by day and "dark" at night,
// drawn by MapLibre GL JS inside Leaflet (the @maplibre/maplibre-gl-leaflet bridge), its labels in the site's language.
// js/app.js starts it once the list and the icons are drawn, so nothing on the page waits for it. When it cannot be
// drawn — no WebGL2, a library file or a style that does not come, no map in 5 seconds, a look's style that does not
// come — the ground is OpenStreetMap's tiles, as before the vector map: the map never stays empty.

const MAP_HOST = 'https://tiles.openfreemap.org/';
const STYLE_BASE = `${MAP_HOST}styles/`;
const STYLES = { light: 'liberty', dark: 'dark' };
const WAIT = 5000; // ms: the style and the first tiles (MapLibre's `load`) — REQ-007's 5 seconds, a hypothesis
const OSM_TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const OSM_CREDIT = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
// ADR-0013 §1's credit, written by the page itself: the tile index's own credit is a file from elsewhere, and an
// outside text never goes into the page as HTML (SPEC-0001 REQ-008)
const OPENFREEMAP_CREDIT = '<a href="https://openfreemap.org/">OpenFreeMap</a> '
  + '<a href="https://www.openmaptiles.org/">&copy; OpenMapTiles</a> '
  + 'Data from <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
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

const state = { kind: 'loading', map: null, layer: null, styles: {}, shown: null, asking: null, timer: 0, watch: null };

// what the map's ground is — 'loading' until MapLibre's first `load`, then 'vector', or 'osm' once it fell back — and
// MapLibre's own map; the tests read MapLibre's style through it (tests/support.py: GROUND_JS)
export function ground() {
  return { kind: state.kind, map: state.layer?.getMaplibreMap() ?? null };
}

// REQ-007's fallback, for the rest of the visit: OpenStreetMap's tiles with their credit (css/style.css darkens them
// at night — the vector map has a dark style of its own)
function fallback(why) {
  if (state.kind === 'osm') return;
  console.warn('the vector map gave way to OpenStreetMap tiles:', why);
  state.kind = 'osm';
  clearTimeout(state.timer);
  state.watch?.disconnect();
  if (state.layer) state.map.removeLayer(state.layer); // its credit goes with it
  state.layer = null;
  L.tileLayer(OSM_TILES, { maxZoom: 19, attribution: OSM_CREDIT, className: 'osm-tiles' }).addTo(state.map);
  state.map.getContainer().dataset.ground = 'osm';
}

// every address MapLibre is about to ask — the tile index, tiles, fonts, pictures, data — must be on OpenFreeMap's host:
// the page's CSP does not reach MapLibre's worker, which fetches tiles and data itself (review S1, 2026-11-09); any
// other address is refused here, on the page, before the request is made
function onlyOpenFreeMap(url) {
  if (!url.startsWith(MAP_HOST)) throw new Error(`not OpenFreeMap's host: ${url}`);
  return { url };
}

function within(ms, promise) {
  return Promise.race([promise, new Promise((_, reject) => {
    setTimeout(() => reject(new Error(`no answer in ${ms} ms`)), ms);
  })]);
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

// the look or the language changed: the look's style — asked once, then kept under that look — with the language's
// labels. A style still on its way is not asked again; when it comes, what is wanted is read afresh, because the look
// may have been switched back meanwhile (review C1)
async function restyle() {
  const gl = state.layer?.getMaplibreMap();
  if (!gl || `${look()} ${language()}` === state.shown) return;
  const want = look();
  const style = state.styles[want];
  if (style) {
    state.shown = `${want} ${language()}`;
    gl.setStyle(localized(style, language()));
    return;
  }
  if (state.asking === want) return;
  state.asking = want;
  try {
    state.styles[want] = await within(WAIT, fetchStyle(STYLES[want]));
  } catch (error) {
    if (look() === want) fallback(error); // the look's style did not come (a look switched back does not need it)
    return;
  } finally {
    state.asking = null;
  }
  restyle();
}

// the bridge's layer with two changes: its credit is the page's own text (the bridge would copy the tile index's, and
// it adds that on MapLibre's `load` without taking it back on removal — a test found it), and it can be taken off the
// map even when MapLibre could not start inside it
function vectorLayer(options) {
  const Layer = L.MaplibreGL.extend({
    getAttribution() {
      return OPENFREEMAP_CREDIT;
    },
    onRemove(map) {
      if (this._glMap) L.MaplibreGL.prototype.onRemove.call(this, map);
      else this._container?.remove();
    },
  });
  return new Layer(options);
}

export async function startGround(map) {
  state.map = map;
  if (!hasWebGL2()) {
    fallback('no WebGL2'); // nothing to fetch: the library is not asked for
    return;
  }
  state.timer = setTimeout(() => fallback(`no map in ${WAIT} ms`), WAIT);
  const first = look();
  try {
    const [style] = await Promise.all([fetchStyle(STYLES[first]), loadLibrary()]);
    if (state.kind === 'osm') return; // too late: the fallback is shown
    state.styles[first] = style;
    state.shown = `${first} ${language()}`;
    state.layer = vectorLayer({ style: localized(style, language()), transformRequest: onlyOpenFreeMap });
    state.layer.addTo(map);
  } catch (error) {
    fallback(error);
    return;
  }
  const gl = state.layer.getMaplibreMap();
  // a vector source that fails before the first `load` — its tile index, or a tile — leaves the map empty, yet MapLibre
  // counts it as loaded and fires `load` all the same (review C2): it is a fallback cause, taken at once, so no frame —
  // where `load` comes from — falls between (the tests see no error left behind)
  gl.on('error', (event) => {
    if (state.kind !== 'loading' || !event.sourceId || gl.getSource(event.sourceId)?.type !== 'vector') return;
    fallback(event.error ?? `source ${event.sourceId} failed`);
  });
  gl.once('load', () => {
    clearTimeout(state.timer);
    state.kind = 'vector';
    map.getContainer().dataset.ground = 'vector';
  });
  state.watch = new MutationObserver(restyle);
  state.watch.observe(document.documentElement, { attributeFilter: ['data-theme', 'lang'] });
  restyle(); // the look or the language may have changed while the library was on its way
}
