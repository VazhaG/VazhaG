// The page: map, fuel choice, the ★ card and prices (SPEC-0001). Texts from the data files are shown only as text
// (textContent, never innerHTML) — REQ-008. The visitor's place stays in this page: it is never sent (REQ-010).
import { FUELS, lang, LANGS, setLang, t } from './i18n.js';
import {
  cheapestNearby, companiesOf, inkOn, lowestFresh, placed, priceRows, routeLinks, stationPrices, stationsFor,
} from './logic.js';
import { logoOf } from './logos.js';

const GEORGIA = [[41.05, 40.0], [43.6, 46.7]]; // south-west and north-east corners: the first view shows it all
const TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const OSM_CREDIT = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const LOCATE = { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }; // REQ-001: 10 seconds at most
const NEAR_ZOOM = 12;
// a station's window opens clear of the filters and the fuel choice on the map's top (SPEC-0005 REQ-003) and of the
// sheet over its lower edge
const POPUP = { autoPanPaddingTopLeft: [12, 128], autoPanPaddingBottomRight: [12, 48] };
// What stays on this phone, and nothing else: the chosen language, the companies switched off (SPEC-0002 REQ-004)
// and the chosen look (SPEC-0004 REQ-006)
const LANG_KEY = 'fuel-map.lang';
const OFF_KEY = 'fuel-map.off';
const THEME_KEY = 'fuel-map.theme';
// Georgian time, written the Georgian way ("30.10 15:00") — the browser's own "ka" format gives "10-30".
const TIME_PARTS = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Tbilisi',
  day: '2-digit',
  month: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

function formatTime(iso) {
  const p = Object.fromEntries(TIME_PARTS.formatToParts(new Date(iso)).map((x) => [x.type, x.value]));
  return `${p.day}.${p.month} ${p.hour}:${p.minute}`;
}

const state = {
  fuel: FUELS[0],
  prices: null,
  stations: null,
  cities: [],
  here: null, // where the ★ is counted from: the visitor's place, or the chosen city's centre
  city: null,
  asking: false, // the city list is shown: no place came from the phone (AC-003)
  map: null,
  markers: null,
  you: null,
  pin: null, // the ★ on the map: the station the card shows (intent §5)
  off: new Set(), // the companies switched off in the badge row (SPEC-0002)
};

function element(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

function priceText(price) {
  return `${price.toFixed(2)} ₾`;
}

function initMap() {
  state.map = L.map('map', { zoomSnap: 0.25, zoomControl: false }).fitBounds(GEORGIA);
  L.control.zoom({ position: 'bottomright' }).addTo(state.map); // the fuel choice floats on the map's top
  L.tileLayer(TILES, { maxZoom: 19, attribution: OSM_CREDIT }).addTo(state.map);
  state.markers = L.layerGroup().addTo(state.map);
  state.map.on('zoomend', () => {
    const near = state.map.getZoom() >= LETTERS_FROM;
    if (near !== state.near) redrawMarks(near); // the letters and the marks come or go
  });
}

function companyPrices(companyId) {
  return (state.prices?.companies ?? []).find((c) => String(c?.id) === companyId);
}

function routeButtons(lat, lng) {
  const links = routeLinks(lat, lng);
  const box = element('div', 'go');
  for (const [key, href] of [['google', links.google], ['waze', links.waze]]) {
    const a = element('a', `go-${key}`, t(`go.${key}`));
    a.href = href;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    box.append(a);
  }
  return box;
}

// REQ-005: the station window — company, name, address, this station's prices and the two buttons.
function stationWindow(s) {
  const box = element('div', 'station-window');
  const title = element('p', 'who');
  title.append(element('strong', '', s.company));
  if (s.name) title.append(` · ${s.name}`);
  box.append(title, element('p', 'address', s.address));
  const list = element('ul', 'prices-here');
  const company = companyPrices(s.companyId);
  for (const fuel of FUELS) {
    for (const p of company ? stationPrices(company, s, fuel, Date.now()) : []) {
      const li = element('li', p.stale ? 'stale' : '', `${p.grade} — ${priceText(p.price)}`);
      if (p.stale) li.append(element('span', 'note', t('price.stale')));
      list.append(li);
    }
  }
  box.append(list.children.length ? list : element('p', 'note', t('station.noPrice')), routeButtons(s.lat, s.lng));
  return box;
}

// SPEC-0002 REQ-002: from the city view on, a station shows its company; from farther away it is a small dot in the
// company's colour, so the whole country's map stays readable.
const LETTERS_FROM = 11;
// SPEC-0005 REQ-007: from the city view a station is a black pin with its company's circle (REQ-001) in its head — a
// square of PIN pixels turned 45° with three round corners, its sharp corner turned down as the tip. The tip is half
// the square's diagonal below its middle, and the marker's anchor is set there, so the tip stands on the station.
const PIN = 36;
const TIP = PIN / 2 + (PIN / 2) * Math.SQRT2;

// SPEC-0003 REQ-003: a light colour (its letters are dark) gets a dark outline by day — the stylesheet uses --edge only
// on the light page and map.
function setEdge(el, color) {
  const ink = inkOn(color);
  if (ink !== '#ffffff') el.style.setProperty('--edge', ink);
}

function stationIcon(s, near) {
  if (near) {
    const pin = element('span', 'pin');
    pin.append(disc({ id: s.companyId, name: s.company, color: s.color })); // a file that fails: its letter, in place
    return L.divIcon({ className: 'station near', html: pin, iconSize: [PIN, PIN], iconAnchor: [PIN / 2, TIP] });
  }
  const dot = element('span');
  dot.style.backgroundColor = s.color;
  setEdge(dot, s.color);
  return L.divIcon({ className: 'station', html: dot, iconSize: [12, 12] });
}

// A marker's look, set again in place: Leaflet keeps the marker and its open window (review C1, C2).
function setStationIcon(marker) {
  const s = marker.options.station;
  marker.setIcon(stationIcon(s, state.near));
  marker.getElement()?.setAttribute('data-company', s.companyId);
}

function renderStations(stations) {
  state.markers.clearLayers();
  state.near = state.map.getZoom() >= LETTERS_FROM;
  for (const s of stationsFor(stations, state.fuel)) {
    const marker = L.marker([s.lat, s.lng], { keyboard: false, station: s });
    marker.setIcon(stationIcon(s, state.near)); // before it is on the map: no element is drawn twice
    marker.bindPopup(() => stationWindow(s), POPUP).addTo(state.markers);
    marker.getElement().dataset.company = s.companyId;
  }
}

// The city view comes or goes: each marker takes its new look in place, so an open station window stays open — a
// redraw would remove the markers, and Leaflet closes a removed marker's window (review C2).
function redrawMarks(near) {
  state.near = near;
  state.markers.eachLayer(setStationIcon);
}

function markBest(b) {
  if (state.pin) state.pin.remove();
  state.pin = null;
  if (!b) return;
  state.pin = L.marker([b.lat, b.lng], {
    icon: L.divIcon({ className: 'best-pin', html: element('span', '', '★'), iconSize: [30, 30] }),
    title: t('best.title'),
    zIndexOffset: 1000,
  })
    .bindPopup(() => stationWindow(b), POPUP)
    .addTo(state.map);
}

// SPEC-0004 REQ-003, REQ-004: each logo file is asked for once on a visit. One loader picture per file asks for it;
// the page's own pictures get the address only once the file has arrived, so the browser gives it from what it
// already holds — however often the row and the map are drawn meanwhile. A file that fails is remembered: its
// company shows its name and letter until the page is opened anew. Only the pictures that waited for it change, each
// in its place, so an open station window, the keyboard's focus and the city list stay as they are (review C1).
const logoLoads = new Map(); // file -> { state: 'loading' | 'ok' | 'failed', waiting: picture -> onFail, loader }

function logoLoad(logo) {
  let load = logoLoads.get(logo.file);
  if (load) return load;
  load = { state: 'loading', waiting: new Map(), loader: new Image() };
  logoLoads.set(logo.file, load);
  load.loader.addEventListener('load', () => {
    load.state = 'ok';
    for (const img of load.waiting.keys()) img.src = logo.file;
    load.waiting.clear();
  }, { once: true });
  load.loader.addEventListener('error', () => {
    load.state = 'failed';
    const fails = [...load.waiting].filter(([img]) => img.isConnected).map(([, onFail]) => onFail);
    load.waiting.clear();
    for (const onFail of fails) onFail();
  }, { once: true });
  load.loader.src = logo.file;
  return load;
}

function usableLogo(id) {
  const logo = logoOf(id);
  return logo && logoLoads.get(logo.file)?.state !== 'failed' ? logo : null;
}

// The picture keeps its size from the start, so the row and the map do not move when the file arrives (REQ-003).
function logoImage(logo, onFail) {
  const img = element('img');
  img.alt = '';
  const load = logoLoad(logo);
  if (load.state === 'ok') img.src = logo.file;
  else load.waiting.set(img, onFail);
  return img;
}

// SPEC-0005 REQ-001: a company's sign — one black circle, the same wherever the company shows; the stylesheet gives
// each place its size. A logo shows its mark, the part that reads small, cut from its own file: the mark's longer side
// is MARK_SHARE of the circle, set in shares of the circle, so the picture fits any size before its file arrives and a
// slow file moves nothing. A company without a logo, or whose file fails, has its colour and first letter instead —
// changed in place, so an open station window and the keyboard's focus stay where they are (review C1).
const MARK_SHARE = 0.6;

function share(v) {
  return `${v * 100}%`;
}

function markImage(logo, onFail) {
  const img = logoImage(logo, onFail);
  const [x, y, w, h] = logo.mark;
  const [fw, fh] = logo.size;
  const k = MARK_SHARE / Math.max(w, h); // the circle's width per pixel of the file
  img.style.width = share(fw * k);
  img.style.height = share(fh * k);
  img.style.left = share((1 - w * k) / 2 - x * k);
  img.style.top = share((1 - h * k) / 2 - y * k);
  // only the mark shows — not the letters beside it (Lukoil's word under its square)
  img.style.clipPath = `inset(${share(y / fh)} ${share((fw - x - w) / fw)} ${share((fh - y - h) / fh)} ${share(x / fw)})`;
  return img;
}

function firstLetter(name) {
  return Array.from(name.trim())[0] ?? '?';
}

function letterDisc(circle, c) {
  const letter = element('span', 'letter', firstLetter(c.name));
  letter.style.backgroundColor = c.color;
  letter.style.color = inkOn(c.color); // REQ-007 of SPEC-0002: the ink that reads best on the colour
  circle.replaceChildren(letter);
}

function disc(c) {
  const circle = element('span', 'disc');
  circle.setAttribute('aria-hidden', 'true'); // a picture of the name — its place says the name in words
  if (logoOf(c.id)?.black) circle.classList.add('black'); // SPEC-0005 REQ-001: black in the light look too
  const logo = usableLogo(c.id);
  if (logo) circle.append(markImage(logo, () => letterDisc(circle, c)));
  else letterDisc(circle, c);
  return circle;
}

// SPEC-0002: the badge row above the ★ card — one per company in the data; its name is what a screen reader says
// (SPEC-0005 REQ-001), its state is aria-pressed.
function renderCompanies() {
  const box = document.getElementById('companies');
  box.setAttribute('aria-label', t('companies.label'));
  box.replaceChildren(...companiesOf(state.prices, state.stations).map((c) => {
    const badge = element('button', 'badge');
    badge.type = 'button';
    badge.dataset.company = c.id;
    badge.setAttribute('aria-pressed', String(!state.off.has(c.id)));
    badge.setAttribute('aria-label', c.name || '?');
    badge.append(disc(c));
    badge.addEventListener('click', () => toggleCompany(c.id));
    return badge;
  }));
  markRowEdges();
}

// SPEC-0003 REQ-005: badges that do not fit scroll in their row (five circles fit a phone — SPEC-0005); an edge with
// more badges beyond it fades (the stylesheet's 24 px strip), and a badge reached from the keyboard is brought clear
// of the strip (the row's padding).
function markRowEdges() {
  const row = document.getElementById('companies');
  row.classList.toggle('more-start', row.scrollLeft > 1);
  row.classList.toggle('more-end', row.scrollWidth - row.clientWidth - row.scrollLeft > 1);
}

function watchRow() {
  const row = document.getElementById('companies');
  row.addEventListener('scroll', markRowEdges, { passive: true });
  row.addEventListener('focusin', (event) => {
    // the keyboard's focus only: a finger's comes before it lifts, and the row must not move under it
    if (event.target.matches(':focus-visible')) event.target.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  });
  window.addEventListener('resize', markRowEdges);
}

// SPEC-0002 REQ-003, SPEC-0005 REQ-003: a company switched off or on, from the badge row or the company filter — the
// map, the ★, the list, the row and the filter follow at once.
function setCompany(id, on) {
  if (on) state.off.delete(id);
  else state.off.add(id);
  saveOff();
  render();
}

function toggleCompany(id) {
  setCompany(id, state.off.has(id));
  // the row was drawn anew: the pressed badge keeps the focus, for the keyboard and the screen reader
  document.querySelector(`#companies [data-company="${CSS.escape(id)}"]`)?.focus();
}

// REQ-004: only the list of companies switched off is kept — those the row still shows; with all of them on, nothing.
function saveOff() {
  const ids = companiesOf(state.prices, state.stations).map((c) => c.id).filter((id) => state.off.has(id));
  try {
    if (ids.length) localStorage.setItem(OFF_KEY, JSON.stringify(ids));
    else localStorage.removeItem(OFF_KEY);
  } catch {
    // a private window or a blocked storage: the choice works for this visit only
  }
}

function savedOff() {
  try {
    const ids = JSON.parse(localStorage.getItem(OFF_KEY) ?? '[]');
    return new Set(Array.isArray(ids) ? ids.filter((id) => typeof id === 'string') : []);
  } catch {
    return new Set(); // blocked or broken: every company on
  }
}

function shown(data) {
  return data && { ...data, companies: (data.companies ?? []).filter((c) => !state.off.has(String(c?.id))) };
}

// REQ-005: every company in the row switched off.
function everyCompanyOff() {
  const ids = companiesOf(state.prices, state.stations).map((c) => c.id);
  return ids.length > 0 && ids.every((id) => state.off.has(id));
}

// AC-003: the fixed city list, in the page's language, alphabetically.
function cityPicker() {
  const wrap = element('div', 'city');
  const label = element('label', '', t('city.ask'));
  label.htmlFor = 'city';
  const select = element('select');
  select.id = 'city';
  select.append(new Option('—', ''));
  const collator = new Intl.Collator(lang());
  const order = state.cities.map((c, i) => [c, i]).sort(([a], [b]) => collator.compare(a[lang()], b[lang()]));
  for (const [c, i] of order) {
    const option = new Option(c[lang()], String(i));
    option.selected = state.city === c;
    select.append(option);
  }
  select.addEventListener('change', () => {
    const c = state.cities[Number(select.value)];
    if (select.value !== '' && c) chooseCity(c);
  });
  wrap.append(label, select);
  return wrap;
}

function chooseCity(c) {
  state.city = c;
  state.here = { lat: c.lat, lng: c.lng };
  if (state.you) state.you.remove();
  state.map.setView([c.lat, c.lng], NEAR_ZOOM);
  render();
}

// REQ-003: the ★ card, once the page knows where to count from.
// REQ-006: an empty result that a switched-off company would have filled says so — not "see the table".
function filteredOut(result, pricesHidden) {
  return !result.best && state.off.size > 0 && (pricesHidden
    || Boolean(cheapestNearby(state.prices, state.stations, state.fuel, state.here, Date.now()).best));
}

const REASON_TEXT = { gasUnknown: 'best.gasUnknown', filtered: 'companies.filtered', none: 'best.none' };

function renderBest(prices, stations, allOff, pricesHidden) {
  const card = document.getElementById('best');
  markBest(null);
  if (!state.here && !state.asking) {
    card.hidden = true;
    return;
  }
  card.hidden = false;
  // SPEC-0005 REQ-004: compact — the title with "all prices" beside it, the company's circle, who and where, the price
  // and the distance on one line, then the two buttons
  const head = element('div', 'best-head');
  head.append(element('h2', 'best-title', t('best.title')));
  const parts = [head];
  if (state.asking) parts.push(cityPicker());
  if (!state.here) {
    card.replaceChildren(...parts);
    return;
  }
  let result = allOff ? { reason: 'allOff' } : cheapestNearby(prices, stations, state.fuel, state.here, Date.now());
  if (!allOff && filteredOut(result, pricesHidden)) result = { reason: 'filtered' };
  markBest(result.best);
  if (result.reason === 'allOff') {
    parts.push(element('p', 'note', t('companies.allOff')));
  } else if (result.best) {
    const b = result.best;
    const row = element('div', 'best-row');
    row.dataset.company = b.companyId;
    const who = element('p', 'who');
    who.append(element('strong', '', b.company), ` · ${b.grade}`);
    if (b.name) who.append(` · ${b.name}`);
    const line = element('p', 'best-line');
    line.append(element('span', 'price', priceText(b.price)),
      element('span', 'km', `${b.distanceKm.toFixed(1)} ${t('unit.km')}`));
    row.append(disc({ id: b.companyId, name: b.company, color: b.color }), who, line);
    parts.push(row);
    if (b.stale) parts.push(element('p', 'note', t('price.stale')));
    parts.push(routeButtons(b.lat, b.lng));
  } else {
    parts.push(element('p', 'note', t(REASON_TEXT[result.reason] ?? 'best.none')));
  }
  const all = element('a', 'to-prices', t('sheet.all'));
  all.href = '#prices-title';
  head.append(all);
  card.replaceChildren(...parts);
}

// The six fuels do not fit a phone's width: the chosen one is scrolled whole into its row — the row, not the page.
function showChosen(box) {
  const chip = box.querySelector('input:checked')?.closest('.chip');
  if (!chip) return;
  const start = chip.offsetLeft - 12;
  const end = chip.offsetLeft + chip.offsetWidth + 12 - box.clientWidth;
  if (box.scrollLeft > start) box.scrollLeft = start;
  else if (box.scrollLeft < end) box.scrollLeft = end;
}

function renderFuels() {
  const box = document.getElementById('fuels');
  for (const old of box.querySelectorAll('label.chip')) old.remove();
  for (const key of FUELS) {
    const label = element('label', 'chip');
    const input = document.createElement('input');
    input.type = 'radio';
    input.name = 'fuel';
    input.value = key;
    input.checked = key === state.fuel;
    input.addEventListener('change', () => chooseFuel(key));
    label.append(input, element('span', '', t(`fuel.${key}`)));
    box.append(label);
  }
  showChosen(box);
}

// The fuel chosen, from the chips or the fuel filter: both show it, and the page follows.
function chooseFuel(key) {
  state.fuel = key;
  const box = document.getElementById('fuels');
  for (const input of box.querySelectorAll('input')) input.checked = input.value === key;
  showChosen(box);
  render();
}

// SPEC-0005 REQ-003: the two filters on the map's top. Each button says what is chosen and opens its panel over the
// map: the companies with a checkbox each — its circle and its name — or the six fuels, to choose one. A panel is
// drawn when it opens and emptied when it closes; while it is open, the page's changes are set on its boxes in place,
// so the keyboard's focus stays where it is.
const FILTERS = ['company', 'fuel'];
let openFilter = null;
let arrowing = false; // the arrows go through the fuels and choose them; only Space, a tap or Esc closes the panel

function filterButton(kind) {
  return document.getElementById(`filter-${kind}`);
}

function filterPanel(kind) {
  return document.getElementById(`panel-${kind}`);
}

function option(input, ...content) {
  const line = element('label', 'option');
  line.append(input, ...content);
  return line;
}

function companyOptions() {
  const set = element('fieldset');
  set.append(element('legend', 'visually-hidden', t('companies.label')));
  for (const c of companiesOf(state.prices, state.stations)) {
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.value = c.id;
    input.checked = !state.off.has(c.id);
    input.addEventListener('change', () => setCompany(c.id, input.checked)); // the panel stays open
    const line = option(input, disc(c), element('span', 'option-name', c.name || '?'));
    line.dataset.company = c.id;
    set.append(line);
  }
  return set;
}

function fuelOptions() {
  const set = element('fieldset');
  set.append(element('legend', 'visually-hidden', t('fuel.legend')));
  for (const key of FUELS) {
    const input = document.createElement('input');
    input.type = 'radio';
    input.name = 'fuel-filter';
    input.value = key;
    input.checked = key === state.fuel;
    // a tap ends the choice — on the fuel already chosen too, which changes nothing (review C1); the arrows go
    // through the fuels and choose each, and the panel stays open
    input.addEventListener('click', () => {
      if (arrowing) return;
      if (state.fuel !== key) chooseFuel(key);
      closePanel();
    });
    input.addEventListener('change', () => {
      if (arrowing) chooseFuel(key);
    });
    set.append(option(input, element('span', 'option-name', t(`fuel.${key}`))));
  }
  return set;
}

function fillPanel(kind) {
  filterPanel(kind).replaceChildren(kind === 'company' ? companyOptions() : fuelOptions());
}

function openPanel(kind) {
  closePanel(false);
  fillPanel(kind);
  filterPanel(kind).hidden = false;
  filterButton(kind).setAttribute('aria-expanded', 'true');
  openFilter = kind;
}

function closePanel(focus = true) {
  if (!openFilter) return;
  const kind = openFilter;
  openFilter = null;
  filterPanel(kind).hidden = true;
  filterPanel(kind).replaceChildren();
  filterButton(kind).setAttribute('aria-expanded', 'false');
  // the page stays where it is, even if the button is out of view (review C2)
  if (focus) filterButton(kind).focus({ preventScroll: true });
}

// The filter's name small above, what is chosen under it — one height in both languages (SPEC-0005 AC-008). The
// dot between them is for a screen reader only: the button says "კომპანია · 4/5".
function filterLabel(kind, name, value) {
  const text = element('span', 'filter-text');
  text.append(element('span', 'filter-name', name));
  if (value) {
    const chosen = element('span', 'filter-value');
    chosen.append(element('span', 'visually-hidden', ' · '), value);
    text.append(chosen);
  }
  filterButton(kind).replaceChildren(text);
}

// The buttons say what is chosen. An open panel's boxes already show it: while a panel is open, the choice changes
// only through its own boxes — a tap or a key anywhere else is a click outside, which closes it. Only the data can
// arrive meanwhile: the company panel is then drawn anew with them.
function syncFilters() {
  const companies = companiesOf(state.prices, state.stations);
  const on = companies.filter((c) => !state.off.has(c.id)).length;
  filterLabel('company', t('filter.company'), companies.length ? `${on}/${companies.length}` : '');
  filterLabel('fuel', t('filter.fuel'), t(`fuel.${state.fuel}`));
  const shown = [...filterPanel('company').querySelectorAll('input')].map((box) => box.value);
  if (openFilter === 'company' && shown.join('\n') !== companies.map((c) => c.id).join('\n')) fillPanel('company');
}

const CONTROLS = 'button, a[href], input, select, textarea, label';

function watchFilters() {
  for (const kind of FILTERS) {
    filterButton(kind).addEventListener('click', () => (openFilter === kind ? closePanel() : openPanel(kind)));
  }
  // Esc closes the open panel, and the focus goes back to its button
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && openFilter) closePanel();
  });
  // a tap outside the open panel and its button closes it — caught on its way down, before the map's own handlers;
  // the focus goes back to the button, unless the tap was on another control, which then has it
  document.addEventListener('click', (event) => {
    if (!openFilter) return;
    const target = event.target;
    if (filterPanel(openFilter).contains(target) || filterButton(openFilter).contains(target)) return;
    closePanel(!target.closest?.(CONTROLS));
  }, true);
  const fuels = filterPanel('fuel');
  fuels.addEventListener('keydown', (event) => {
    arrowing = event.key.startsWith('Arrow');
    // Space or Enter on the fuel the arrows reached ends the choice: a checked radio fires no click of its own
    if ((event.key === ' ' || event.key === 'Enter') && event.target.matches('input')) {
      event.preventDefault();
      closePanel();
    }
  });
  fuels.addEventListener('keyup', () => {
    arrowing = false;
  });
}

async function loadJson(name) {
  try {
    const r = await fetch(`data/${name}`, { cache: 'no-cache' });
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}

function setStatus(text) {
  document.getElementById('status').textContent = text;
}

// SPEC-0005 REQ-005: one line of the price list — the company's circle; its name, with "cheapest" beside it on the
// list's lowest fresh price; the grade; when the price was read, whose time that is and whether it is old; the price.
function priceLine(row, low) {
  const cheap = !row.stale && row.price === low;
  const li = element('li', [row.stale && 'stale', cheap && 'cheap'].filter(Boolean).join(' '));
  li.dataset.company = row.companyId;
  const name = element('p', 'price-name');
  name.append(element('strong', '', row.company));
  if (cheap) name.append(' ', element('span', 'tag', t('list.cheapest')));
  const when = [`${t('table.time')} ${formatTime(row.time)}`];
  if (row.basis === 'source') when.push(t('time.source'));
  if (row.stale) when.push(t('price.stale'));
  const who = element('div', 'price-who');
  who.append(name, element('p', 'grade', row.grade), element('p', 'time', when.join(' · ')));
  li.append(disc({ id: row.companyId, name: row.company, color: row.color }), who,
    element('span', 'price', priceText(row.price)));
  return li;
}

function render() {
  const prices = shown(state.prices);
  const stations = shown(state.stations);
  const allOff = everyCompanyOff();
  const rows = priceRows(prices, state.fuel, Date.now());
  const pricesHidden = !rows.length && state.off.size > 0 && priceRows(state.prices, state.fuel, Date.now()).length > 0;
  renderCompanies();
  syncFilters();
  renderStations(stations);
  renderBest(prices, stations, allOff, pricesHidden);
  // SPEC-0005 REQ-005: the list of the chosen fuel; a message stands in its place, under its title
  const list = document.getElementById('price-list');
  if (!state.prices) {
    list.replaceChildren();
    setStatus(t('status.noPrices'));
    return;
  }
  if (allOff) {
    list.replaceChildren();
    setStatus(t('companies.allOff'));
    return;
  }
  const low = lowestFresh(rows);
  list.replaceChildren(...rows.map((row) => priceLine(row, low)));
  setStatus(rows.length ? '' : t(pricesHidden ? 'companies.filtered' : 'status.noFuelPrice'));
}

function showHere(lat, lng) {
  state.here = { lat, lng };
  state.map.setView([lat, lng], NEAR_ZOOM);
  if (state.you) state.you.remove();
  state.you = L.circleMarker([lat, lng], {
    radius: 6,
    color: '#ffffff',
    weight: 2,
    fillColor: '#2563eb',
    fillOpacity: 1,
    className: 'you',
    interactive: false,
  }).addTo(state.map);
  render();
}

function askCity() {
  if (state.here && !state.city) return; // the phone answered meanwhile
  state.asking = true;
  render();
}

// REQ-001: ask the phone; a refusal, an error or 10 seconds without an answer bring the city list (AC-003).
function locate() {
  if (!('geolocation' in navigator)) {
    askCity();
    return;
  }
  const timer = setTimeout(askCity, LOCATE.timeout);
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      clearTimeout(timer);
      if (!state.city) showHere(pos.coords.latitude, pos.coords.longitude);
    },
    () => {
      clearTimeout(timer);
      askCity();
    },
    LOCATE,
  );
}

// REQ-009: the texts the page itself writes, in the chosen language.
function applyStatic() {
  document.documentElement.lang = lang();
  document.title = t('title.page');
  for (const el of document.querySelectorAll('[data-i18n]')) el.textContent = t(el.dataset.i18n);
  document.querySelector('.lang').setAttribute('aria-label', t('lang.group'));
  document.getElementById('theme').setAttribute('aria-label', t('theme.label'));
  for (const button of document.querySelectorAll('.lang button')) {
    button.setAttribute('aria-pressed', String(button.dataset.lang === lang()));
  }
}

function setLanguage(code) {
  setLang(code);
  try {
    localStorage.setItem(LANG_KEY, lang());
  } catch {
    // a private window or a blocked storage: the choice simply is not remembered
  }
  state.map.closePopup();
  applyStatic();
  renderFuels();
  render(); // an open panel closed already: the language button's tap was a tap outside it
}

// SPEC-0004 REQ-006: the visitor's look — 'light' or 'dark' once chosen (kept on the phone; with a blocked storage, for
// this visit only), else null and the phone's own setting rules. js/theme.js drew the first look the same way.
let chosenTheme = null;
const phoneDark = window.matchMedia('(prefers-color-scheme: dark)');

function savedTheme() {
  try {
    const kept = localStorage.getItem(THEME_KEY);
    return kept === 'light' || kept === 'dark' ? kept : null;
  } catch {
    return null;
  }
}

function applyTheme() {
  const dark = (chosenTheme ?? (phoneDark.matches ? 'dark' : 'light')) === 'dark';
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  const button = document.getElementById('theme');
  button.setAttribute('aria-pressed', String(dark)); // its name stays "dark mode": pressed means dark
}

function toggleTheme() {
  chosenTheme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  try {
    localStorage.setItem(THEME_KEY, chosenTheme);
  } catch {
    // a private window or a blocked storage: the choice holds for this visit only
  }
  applyTheme();
}

function savedLanguage() {
  try {
    const code = localStorage.getItem(LANG_KEY);
    return LANGS.includes(code) ? code : null;
  } catch {
    return null;
  }
}

function validCities(data) {
  const collator = new Intl.Collator('ka');
  return (data?.cities ?? [])
    .filter((c) => typeof c?.ka === 'string' && typeof c.en === 'string' && placed(c.lat, c.lng))
    .sort((a, b) => collator.compare(a.ka, b.ka));
}

async function main() {
  setLang(savedLanguage() ?? 'ka');
  state.off = savedOff();
  chosenTheme = savedTheme();
  applyTheme();
  document.getElementById('theme').addEventListener('click', toggleTheme);
  phoneDark.addEventListener('change', () => {
    if (!chosenTheme) applyTheme(); // no choice of their own: the page follows the phone
  });
  applyStatic();
  for (const button of document.querySelectorAll('.lang button')) {
    button.addEventListener('click', () => setLanguage(button.dataset.lang));
  }
  watchRow();
  watchFilters();
  initMap();
  renderFuels();
  syncFilters();
  setStatus(t('status.loading'));
  let cities;
  [state.prices, state.stations, cities] = await Promise.all(
    ['prices.json', 'stations.json', 'cities.json'].map(loadJson),
  );
  state.cities = validCities(cities);
  render();
  locate();
}

main();
