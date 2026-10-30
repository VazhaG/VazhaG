// The page: map, fuel choice and prices (SPEC-0001). Texts from the data files are shown only as text
// (textContent, never innerHTML) — REQ-008.
import { FUELS, t } from './i18n.js';
import { priceRows, stationsFor } from './logic.js';

const GEORGIA = [[41.05, 40.0], [43.6, 46.7]]; // south-west and north-east corners: the first view shows it all
const TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const OSM_CREDIT = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
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

const state = { fuel: FUELS[0], prices: null, stations: null, markers: null };

function initMap() {
  const map = L.map('map', { zoomSnap: 0.25 }).fitBounds(GEORGIA);
  L.tileLayer(TILES, { maxZoom: 19, attribution: OSM_CREDIT }).addTo(map);
  state.markers = L.layerGroup().addTo(map);
  return map;
}

function renderStations() {
  state.markers.clearLayers();
  for (const s of stationsFor(state.stations, state.fuel)) {
    L.circleMarker([s.lat, s.lng], {
      radius: 7,
      color: '#ffffff',
      weight: 1.5,
      fillColor: s.color,
      fillOpacity: 0.95,
      className: 'station',
    }).addTo(state.markers);
  }
}

function renderFuels() {
  const box = document.getElementById('fuels');
  for (const key of FUELS) {
    const label = document.createElement('label');
    label.className = 'chip';
    const input = document.createElement('input');
    input.type = 'radio';
    input.name = 'fuel';
    input.value = key;
    input.checked = key === state.fuel;
    input.addEventListener('change', () => {
      state.fuel = key;
      render();
    });
    const span = document.createElement('span');
    span.textContent = t(`fuel.${key}`);
    label.append(input, span);
    box.append(label);
  }
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

function element(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

function rowElement(row) {
  const tr = element('tr', row.stale ? 'stale' : '');
  const dot = element('span', 'dot');
  dot.style.backgroundColor = row.color;
  const who = element('td', 'who');
  who.append(dot, element('strong', '', row.company), element('span', 'grade', row.grade));
  const when = element('td', 'time', formatTime(row.time));
  if (row.stale) when.append(element('span', 'note', t('price.stale')));
  tr.append(who, element('td', 'price', `${row.price.toFixed(2)} ₾`), when);
  return tr;
}

function render() {
  renderStations();
  const body = document.querySelector('#price-table tbody');
  if (!state.prices) {
    body.replaceChildren();
    setStatus(t('status.noPrices'));
    return;
  }
  const rows = priceRows(state.prices, state.fuel, Date.now());
  body.replaceChildren(...rows.map(rowElement));
  setStatus(rows.length ? '' : t('status.noFuelPrice'));
}

async function main() {
  initMap();
  renderFuels();
  setStatus(t('status.loading'));
  [state.prices, state.stations] = await Promise.all([loadJson('prices.json'), loadJson('stations.json')]);
  render();
}

main();
