// Screens: vehicle form and list, trip form and list, void buttons.
// Talks only to api.js. Open with ?transport=mock to use the test fixtures.

import { createApi } from './api.js';

const $ = (id) => document.getElementById(id);

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'class') node.className = v;
    else if (k === 'dataset') Object.assign(node.dataset, v);
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of children) if (c !== null && c !== undefined) node.append(c);
  return node;
}

function today() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

const km = (n) => `${Number(n).toLocaleString('en-US')} km`;

function showMessage(node, text) {
  node.textContent = text || '';
  node.hidden = !text;
}

function markInvalid(form, field) {
  for (const input of form.querySelectorAll('[aria-invalid]')) input.removeAttribute('aria-invalid');
  const target = field && form.querySelector(`[name="${field}"]`);
  if (target) {
    target.setAttribute('aria-invalid', 'true');
    target.focus();
  }
}

// Two-tap void: the first tap arms the button, the second confirms.
function voidButton(label, onConfirm) {
  const btn = el('button', { type: 'button', class: 'secondary', 'aria-label': label }, 'Void');
  btn.addEventListener('click', async () => {
    if (!btn.classList.contains('confirm')) {
      btn.classList.add('confirm');
      btn.textContent = 'Confirm void';
      btn.setAttribute('aria-label', `Confirm ${label.charAt(0).toLowerCase()}${label.slice(1)}`);
      return;
    }
    btn.disabled = true;
    await onConfirm();
  });
  return btn;
}

let api;
let purposes = [];

async function must(promise) {
  const res = await promise;
  if (!res.ok) throw new Error(res.error.message);
  return res.data;
}

async function refreshVehicles() {
  const vehicles = await must(api.listVehicles({ includeInactive: true }));
  const active = vehicles.filter((v) => v.is_active);

  const list = $('vehicle-list');
  list.replaceChildren(
    ...vehicles.map((v) =>
      el('li', { class: `card${v.is_active ? '' : ' voided'}`, dataset: { id: v.id } },
        el('div', { class: 'info' },
          el('div', { class: 'title' }, `${v.name} · ${v.plate}`,
            v.is_active ? null : el('span', { class: 'status' }, 'Voided')),
          el('div', { class: 'meta' }, `${v.fuel_type} · started at ${km(v.start_odometer_km)}`)),
        v.is_active ? voidButton(`Void vehicle ${v.plate}`, () => onVoidVehicle(v.id)) : null)),
  );
  $('vehicles-empty').hidden = vehicles.length > 0;

  const select = $('trip-vehicle');
  const previous = select.value;
  select.replaceChildren(
    el('option', { value: '' }, active.length ? 'Choose a vehicle' : 'Add a vehicle first'),
    ...active.map((v) => el('option', { value: v.id }, `${v.name} · ${v.plate}`)),
  );
  if (active.some((v) => v.id === previous)) select.value = previous;
  else if (active.length === 1) select.value = active[0].id;
  await fillStartKm();
}

async function refreshTrips() {
  const trips = await must(api.listTrips());
  $('trip-list').replaceChildren(
    ...trips.map((t) => {
      const voided = t.status === 'Voided';
      return el('li', { class: `card trip${voided ? ' voided' : ''}`, dataset: { id: t.id, status: t.status } },
        el('div', { class: 'info' },
          el('div', { class: 'title' }, `${t.trip_date} · ${t.destination}`,
            voided ? el('span', { class: 'status' }, 'Voided') : null),
          el('div', { class: 'meta' }, `${t.vehicle_name} · ${t.purpose} · ${km(t.start_km)} → ${km(t.end_km)}`)),
        el('div', { class: 'km' }, km(t.distance_km)),
        voided ? null : voidButton(`Void trip ${t.trip_date} ${t.destination}`, () => onVoidTrip(t.id)));
    }),
  );
  $('trips-empty').hidden = trips.length > 0;
}

async function fillStartKm() {
  const id = $('trip-vehicle').value;
  if (!id) return;
  const res = await api.lastEndKm(id);
  if (res.ok) $('trip-start').value = res.data;
}

async function onVoidVehicle(id) {
  const res = await api.voidVehicle(id);
  if (!res.ok) showMessage($('vehicle-error'), res.error.message);
  await refreshVehicles();
  await refreshTrips();
}

async function onVoidTrip(id) {
  const res = await api.voidTrip(id);
  if (!res.ok) showMessage($('trip-error'), res.error.message);
  await refreshTrips();
  await fillStartKm();
}

async function onAddVehicle(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const res = await api.addVehicle(Object.fromEntries(new FormData(form)));
  markInvalid(form, res.ok ? null : res.error.field);
  showMessage($('vehicle-error'), res.ok ? '' : res.error.message);
  if (!res.ok) return;
  form.reset();
  await refreshVehicles();
  $('trip-vehicle').value = res.data.id;
  await fillStartKm();
}

async function onAddTrip(event) {
  event.preventDefault();
  const form = event.currentTarget;
  showMessage($('trip-ok'), '');
  const res = await api.addTrip(Object.fromEntries(new FormData(form)));
  markInvalid(form, res.ok ? null : res.error.field);
  showMessage($('trip-error'), res.ok ? '' : res.error.message);
  if (!res.ok) return;
  $('trip-end').value = '';
  $('trip-destination').value = '';
  showMessage($('trip-ok'), `Saved: ${km(res.data.end_km - res.data.start_km)}.`);
  await refreshTrips();
  await fillStartKm();
}

async function init() {
  const transport = new URLSearchParams(location.search).get('transport') || 'local';
  try {
    api = await createApi({
      transport,
      storage: transport === 'mock' ? window.sessionStorage : window.localStorage,
      loadFixtures: async () => {
        const res = await fetch('../tests/fixtures/seed.json');
        if (!res.ok) throw new Error(`Could not load test fixtures (${res.status}).`);
        return res.json();
      },
    });
  } catch (e) {
    showMessage($('fatal'), `The app could not start: ${e.message}`);
    return;
  }

  if (transport === 'mock') {
    $('mode').textContent = 'Test data (mock)';
    $('mode').hidden = false;
  }

  $('veh-fuel').replaceChildren(...api.fuelTypes.map((f) => el('option', { value: f }, f)));
  purposes = await must(api.listPurposes());
  $('trip-purpose').replaceChildren(...purposes.map((p) => el('option', { value: p.id }, p.value)));
  $('trip-date').value = today();

  $('vehicle-form').addEventListener('submit', onAddVehicle);
  $('trip-form').addEventListener('submit', onAddTrip);
  $('trip-vehicle').addEventListener('change', fillStartKm);

  await refreshVehicles();
  await refreshTrips();
  document.body.dataset.ready = 'true';
}

init().catch((e) => showMessage($('fatal'), `Something went wrong: ${e.message}`));
