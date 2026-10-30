import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createApi, MOCK_STORAGE_KEY } from '../../app/api.js';
import { memoryStorage, STORAGE_KEY } from '../../app/repository.js';

const fixtures = JSON.parse(readFileSync(new URL('../fixtures/seed.json', import.meta.url), 'utf8'));
const keys = (o) => Object.keys(o).sort();

async function addSample(api) {
  const veh = await api.addVehicle({ name: 'Test Van', plate: 'TEST-002', fuel_type: 'Diesel', start_odometer_km: 5000 });
  const work = (await api.listPurposes()).data.find((p) => p.value === 'Work');
  const trip = await api.addTrip({
    vehicle_id: veh.data.id, trip_date: '2026-02-01', start_km: 5000, end_km: 5042,
    purpose_id: work.id, destination: 'Test Site',
  });
  return { veh, trip };
}

test('mock transport loads the fixtures', async () => {
  const api = await createApi({ transport: 'mock', fixtures });
  const vehicles = (await api.listVehicles()).data;
  assert.deepEqual(vehicles.map((v) => v.plate), ['TEST-001']);
  const trips = (await api.listTrips()).data;
  assert.equal(trips.length, 1);
  assert.equal(trips[0].distance_km, 12);
});

test('mock fixtures are loaded once and can come from a loader', async () => {
  const storage = memoryStorage();
  let loads = 0;
  const loadFixtures = async () => { loads++; return fixtures; };
  await createApi({ transport: 'mock', storage, loadFixtures });
  const again = await createApi({ transport: 'mock', storage, loadFixtures });
  assert.equal(loads, 1);
  assert.equal((await again.listVehicles()).data.length, 1);
  assert.ok(storage.getItem(MOCK_STORAGE_KEY));
  assert.equal(storage.getItem(STORAGE_KEY), null, 'mock never writes the real store');
});

test('local transport keeps data in the given storage across instances', async () => {
  const storage = memoryStorage();
  const api = await createApi({ transport: 'local', storage });
  assert.equal((await api.listVehicles()).data.length, 0);
  await addSample(api);
  const reopened = await createApi({ transport: 'local', storage });
  assert.equal((await reopened.listTrips()).data[0].distance_km, 42);
});

test('both transports return the same shapes', async () => {
  const local = await createApi({ transport: 'local', storage: memoryStorage() });
  const mock = await createApi({ transport: 'mock', fixtures });
  const a = await addSample(local);
  const b = await addSample(mock);
  assert.deepEqual(keys(a.veh), keys(b.veh));
  assert.deepEqual(keys(a.veh.data), keys(b.veh.data));
  assert.deepEqual(keys(a.trip.data), keys(b.trip.data));
  for (const name of ['listVehicles', 'listPurposes', 'listTrips']) {
    const [x, y] = [await local[name](), await mock[name]()];
    assert.equal(x.ok, true);
    assert.equal(y.ok, true);
    assert.deepEqual(keys(x.data[0]), keys(y.data[0]), name);
  }
  assert.deepEqual(keys(await local.lastEndKm(a.veh.data.id)), keys(await mock.lastEndKm(b.veh.data.id)));
});

test('validation errors come back as an error envelope', async () => {
  const api = await createApi({ transport: 'mock', fixtures });
  const bike = (await api.listVehicles()).data[0];
  const work = (await api.listPurposes()).data[0];
  const res = await api.addTrip({
    vehicle_id: bike.id, trip_date: '2026-01-06', start_km: 1012, end_km: 1000,
    purpose_id: work.id, destination: 'Test Office',
  });
  assert.equal(res.ok, false);
  assert.equal(res.error.code, 'VALIDATION');
  assert.equal(res.error.field, 'end_km');
  assert.match(res.error.message, /below the start reading/);
});

test('void goes through the API and is reflected in the list', async () => {
  const api = await createApi({ transport: 'mock', fixtures });
  const trip = (await api.listTrips()).data[0];
  const res = await api.voidTrip(trip.id);
  assert.equal(res.ok, true);
  assert.equal((await api.listTrips()).data[0].status, 'Voided');
  assert.equal((await api.voidTrip(trip.id)).ok, false);
});

test('an unknown transport is refused', async () => {
  await assert.rejects(createApi({ transport: 'rest' }), /Unknown transport/);
});

test('export: local and mock return the same shapes', async () => {
  const local = await createApi({ transport: 'local', storage: memoryStorage(), now: () => new Date('2026-03-04T10:00:00Z') });
  const mock = await createApi({ transport: 'mock', storage: memoryStorage(), fixtures, now: () => new Date('2026-03-04T10:00:00Z') });
  for (const api of [local, mock]) {
    const tables = await api.listExportTables();
    assert.equal(tables.ok, true);
    assert.deepEqual(tables.data.map((t) => t.table), ['vehicles', 'trips', 'lookups', 'audit_log']);
    for (const t of tables.data) assert.deepEqual(keys(t), ['rows', 'table']);
    const out = await api.exportCsv('lookups');
    assert.equal(out.ok, true);
    assert.deepEqual(keys(out.data), ['csv', 'filename', 'rows', 'table']);
    assert.equal(out.data.filename, 'odometer-lookups-2026-03-04.csv');
    assert.equal(out.data.rows, 3);
  }
  assert.equal((await mock.exportCsv('vehicles')).data.rows, 1);
  assert.equal((await mock.exportCsv('trips')).data.rows, 1);
});

test('export: an unknown table returns the error shape', async () => {
  const api = await createApi({ transport: 'local', storage: memoryStorage() });
  const res = await api.exportCsv('fuel');
  assert.equal(res.ok, false);
  assert.deepEqual(keys(res.error), ['code', 'field', 'message']);
  assert.equal(res.error.code, 'VALIDATION');
  assert.equal(res.error.field, 'table');
});
