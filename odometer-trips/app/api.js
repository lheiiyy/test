// API client: the only thing screens call. Every call is async and returns
// { ok: true, data } or { ok: false, error: { code, field, message } },
// so later transports (appsscript, rest) can keep the same shape.
//
// transport 'local': browser localStorage (version 1).
// transport 'mock':  fixtures from tests/fixtures/seed.json in a separate store
//                    (sessionStorage in the browser, memory in Node).

import { createRepository, memoryStorage, STORAGE_KEY } from './repository.js';
import { createServices, ValidationError, FUEL_TYPES } from './services.js';

export const TRANSPORTS = ['local', 'mock'];
export const MOCK_STORAGE_KEY = 'odometer-trips:mock';

function seedFromFixtures(services, fixtures) {
  const byPlate = new Map();
  for (const v of fixtures.vehicles ?? []) {
    const row = services.addVehicle(v);
    byPlate.set(row.plate, row.id);
  }
  const purposes = new Map(services.listPurposes().map((p) => [p.value, p.id]));
  for (const t of fixtures.trips ?? []) {
    const { vehicle_plate, purpose, ...rest } = t;
    services.addTrip({ ...rest, vehicle_id: byPlate.get(vehicle_plate), purpose_id: purposes.get(purpose) });
  }
}

export async function createApi({ transport = 'local', storage, fixtures, loadFixtures, user, now } = {}) {
  if (!TRANSPORTS.includes(transport)) throw new Error(`Unknown transport: ${transport}`);

  let store = storage;
  if (!store) store = transport === 'local' ? globalThis.localStorage : memoryStorage();
  if (!store) throw new Error('Browser storage is not available.');

  const key = transport === 'mock' ? MOCK_STORAGE_KEY : STORAGE_KEY;
  const services = createServices(createRepository({ storage: store, key, user, now }));

  if (transport === 'mock' && services.listVehicles({ includeInactive: true }).length === 0) {
    const data = fixtures ?? (loadFixtures ? await loadFixtures() : {});
    seedFromFixtures(services, data);
  }

  const call = (fn) => async (...args) => {
    try {
      return { ok: true, data: fn(...args) };
    } catch (e) {
      if (e instanceof ValidationError) {
        return { ok: false, error: { code: 'VALIDATION', field: e.field, message: e.message } };
      }
      return { ok: false, error: { code: 'ERROR', field: null, message: e?.message ?? String(e) } };
    }
  };

  return {
    transport,
    fuelTypes: [...FUEL_TYPES],
    listVehicles: call((opts) => services.listVehicles(opts)),
    addVehicle: call((input) => services.addVehicle(input)),
    voidVehicle: call((id) => services.voidVehicle(id)),
    listPurposes: call(() => services.listPurposes()),
    lastEndKm: call((vehicleId) => services.lastEndKm(vehicleId)),
    listTrips: call(() => services.listTrips()),
    addTrip: call((input) => services.addTrip(input)),
    voidTrip: call((id) => services.voidTrip(id)),
  };
}
