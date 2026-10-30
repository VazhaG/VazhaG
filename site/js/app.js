// The page: map, fuel choice, the ★ card and prices (SPEC-0001). Texts from the data files are shown only as text
// (textContent, never innerHTML) — REQ-008. The visitor's place stays in this page: it is never sent (REQ-010).
import { FUELS, lang, LANGS, setLang, t } from './i18n.js';
import {
  cheapestNearby, companiesOf, inkOn, placed, priceRows, routeLinks, stationPrices, stationsFor,
} from './logic.js';

const GEORGIA = [[41.05, 40.0], [43.6, 46.7]]; // south-west and north-east corners: the first view shows it all
const TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const OSM_CREDIT = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const LOCATE = { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 }; // REQ-001: 10 seconds at most
const NEAR_ZOOM = 12;
// a station's window opens clear of the fuel choice on the map's top and of the sheet over its lower edge
const POPUP = { autoPanPaddingTopLeft: [12, 72], autoPanPaddingBottomRight: [12, 48] };
const LANG_KEY = 'fuel-map.lang'; // the chosen language stays on this phone; nothing else is stored
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

function renderStations(stations) {
  state.markers.clearLayers();
  for (const s of stationsFor(stations, state.fuel)) {
    L.circleMarker([s.lat, s.lng], {
      radius: 7,
      color: '#ffffff',
      weight: 1.5,
      fillColor: s.color,
      fillOpacity: 0.95,
      className: 'station',
    })
      .bindPopup(() => stationWindow(s), POPUP)
      .addTo(state.markers);
  }
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

// SPEC-0002: the badge row above the ★ card — one per company in the data, its colour and name, text only.
function renderCompanies() {
  const box = document.getElementById('companies');
  box.setAttribute('aria-label', t('companies.label'));
  box.replaceChildren(...companiesOf(state.prices, state.stations).map((c) => {
    const badge = element('button', 'badge', c.name || '?');
    badge.type = 'button';
    badge.dataset.company = c.id;
    badge.setAttribute('aria-pressed', String(!state.off.has(c.id)));
    badge.style.setProperty('--company', c.color);
    badge.style.setProperty('--ink', inkOn(c.color));
    badge.addEventListener('click', () => toggleCompany(c.id));
    return badge;
  }));
}

// REQ-003: a badge switches its company off or on — the map, the ★ and the table follow at once.
function toggleCompany(id) {
  if (state.off.has(id)) state.off.delete(id);
  else state.off.add(id);
  render();
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
function renderBest(prices, stations, allOff) {
  const card = document.getElementById('best');
  markBest(null);
  if (!state.here && !state.asking) {
    card.hidden = true;
    return;
  }
  card.hidden = false;
  const parts = [element('h2', 'best-title', t('best.title'))];
  if (state.asking) parts.push(cityPicker());
  if (!state.here) {
    card.replaceChildren(...parts);
    return;
  }
  const result = allOff ? { reason: 'allOff' } : cheapestNearby(prices, stations, state.fuel, state.here, Date.now());
  markBest(result.best);
  if (result.reason === 'allOff') {
    parts.push(element('p', 'note', t('companies.allOff')));
  } else if (result.best) {
    const b = result.best;
    const who = element('p', 'who');
    const dot = element('span', 'dot');
    dot.style.backgroundColor = b.color;
    who.append(dot, element('strong', '', b.company), ` · ${b.grade}`);
    if (b.name) who.append(` · ${b.name}`);
    const line = element('p', 'best-line');
    line.append(element('span', 'price', priceText(b.price)), ` · ${b.distanceKm.toFixed(1)} ${t('unit.km')}`);
    parts.push(who, line);
    if (b.stale) parts.push(element('p', 'note', t('price.stale')));
    parts.push(routeButtons(b.lat, b.lng));
  } else {
    parts.push(element('p', 'note', t(result.reason === 'gasUnknown' ? 'best.gasUnknown' : 'best.none')));
  }
  const all = element('a', 'to-prices', t('sheet.all'));
  all.href = '#prices-title';
  parts.push(all);
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
    input.addEventListener('change', () => {
      state.fuel = key;
      showChosen(box);
      render();
    });
    label.append(input, element('span', '', t(`fuel.${key}`)));
    box.append(label);
  }
  showChosen(box);
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

function rowElement(row) {
  const tr = element('tr', row.stale ? 'stale' : '');
  const dot = element('span', 'dot');
  dot.style.backgroundColor = row.color;
  const who = element('td', 'who');
  who.append(dot, element('strong', '', row.company), element('span', 'grade', row.grade));
  const when = element('td', 'time', formatTime(row.time));
  if (row.basis === 'source') when.append(element('span', 'note', t('time.source')));
  if (row.stale) when.append(element('span', 'note', t('price.stale')));
  tr.append(who, element('td', 'price', priceText(row.price)), when);
  return tr;
}

function render() {
  const prices = shown(state.prices);
  const stations = shown(state.stations);
  const allOff = everyCompanyOff();
  renderCompanies();
  renderStations(stations);
  renderBest(prices, stations, allOff);
  const body = document.querySelector('#price-table tbody');
  if (!state.prices) {
    body.replaceChildren();
    setStatus(t('status.noPrices'));
    return;
  }
  if (allOff) {
    body.replaceChildren();
    setStatus(t('companies.allOff'));
    return;
  }
  const rows = priceRows(prices, state.fuel, Date.now());
  body.replaceChildren(...rows.map(rowElement));
  setStatus(rows.length ? '' : t('status.noFuelPrice'));
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
  render();
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
  applyStatic();
  for (const button of document.querySelectorAll('.lang button')) {
    button.addEventListener('click', () => setLanguage(button.dataset.lang));
  }
  initMap();
  renderFuels();
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
