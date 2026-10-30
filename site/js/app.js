// The page: map, fuel choice and prices (SPEC-0001). Texts from the data files are shown only as text
// (textContent, never innerHTML) — REQ-008.
import { FUELS, t } from './i18n.js';

const GEORGIA = [42.3, 43.4];
const TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const OSM_CREDIT = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

const state = { fuel: FUELS[0], prices: null };

function initMap() {
  const map = L.map('map').setView(GEORGIA, 7);
  L.tileLayer(TILES, { maxZoom: 19, attribution: OSM_CREDIT }).addTo(map);
  return map;
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

function render() {
  if (!state.prices) {
    setStatus(t('status.noPrices'));
  }
}

async function main() {
  initMap();
  renderFuels();
  setStatus(t('status.loading'));
  state.prices = await loadJson('prices.json');
  render();
}

main();
