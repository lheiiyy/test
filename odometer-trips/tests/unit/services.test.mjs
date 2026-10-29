import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRepository, memoryStorage } from '../../app/repository.js';
import { createServices, ValidationError, distanceKm } from '../../app/services.js';

function setup() {
  const repo = createRepository({ storage: memoryStorage(), user: 'tester' });
  const svc = createServices(repo);
  const bike = svc.addVehicle({ name: 'Test Bike', plate: 'TEST-001', fuel_type: 'Gasoline', start_odometer_km: '1000' });
  const work = svc.listPurposes().find((p) => p.value === 'Work');
  const trip = (over = {}) => ({
    vehicle_id: bike.id, trip_date: '2026-01-05', start_km: 1000, end_km: 1012,
    purpose_id: work.id, destination: 'Test Office', ...over,
  });
  return { repo, svc, bike, work, trip };
}

function rejects(fn, field, pattern) {
  assert.throws(fn, (e) => {
    assert.ok(e instanceof ValidationError, `expected ValidationError, got ${e}`);
    if (field) assert.equal(e.field, field);
    if (pattern) assert.match(e.message, pattern);
    return true;
  });
}

test('adds a vehicle with a whole-km starting odometer', () => {
  const { bike } = setup();
  assert.match(bike.id, /^VEH-/);
  assert.equal(bike.start_odometer_km, 1000);
  assert.equal(bike.plate, 'TEST-001');
});

test('vehicle input is validated', () => {
  const { svc } = setup();
  const ok = { name: 'Test Van', plate: 'TEST-002', fuel_type: 'Diesel', start_odometer_km: 0 };
  rejects(() => svc.addVehicle({ ...ok, name: '  ' }), 'name');
  rejects(() => svc.addVehicle({ ...ok, plate: '' }), 'plate');
  rejects(() => svc.addVehicle({ ...ok, fuel_type: 'Steam' }), 'fuel_type');
  rejects(() => svc.addVehicle({ ...ok, start_odometer_km: '12.5' }), 'start_odometer_km', /whole/);
  rejects(() => svc.addVehicle({ ...ok, start_odometer_km: -1 }), 'start_odometer_km');
  rejects(() => svc.addVehicle({ ...ok, start_odometer_km: '' }), 'start_odometer_km', /required/);
  rejects(() => svc.addVehicle({ ...ok, plate: 'test-001' }), 'plate', /already/);
});

test('adds a trip with date, vehicle, readings, purpose and destination', () => {
  const { svc, trip } = setup();
  const t = svc.addTrip(trip());
  assert.match(t.id, /^TRP-/);
  assert.equal(t.status, 'Closed');
  assert.equal(t.trip_date, '2026-01-05');
  assert.equal(t.destination, 'Test Office');
});

test('rejects an end reading below the start reading', () => {
  const { svc, trip } = setup();
  rejects(() => svc.addTrip(trip({ start_km: 1000, end_km: 999 })), 'end_km', /below the start reading/);
});

test("rejects a start reading below the vehicle's last end reading", () => {
  const { svc, trip } = setup();
  rejects(() => svc.addTrip(trip({ start_km: 999, end_km: 1005 })), 'start_km', /last end reading \(1000 km\)/);
  svc.addTrip(trip({ start_km: 1000, end_km: 1050 }));
  assert.equal(svc.lastEndKm(trip().vehicle_id), 1050);
  rejects(() => svc.addTrip(trip({ start_km: 1040, end_km: 1060 })), 'start_km', /1050 km/);
  svc.addTrip(trip({ start_km: 1050, end_km: 1060 }));
});

test('trip input is validated', () => {
  const { svc, trip } = setup();
  rejects(() => svc.addTrip(trip({ trip_date: '05/01/2026' })), 'trip_date');
  rejects(() => svc.addTrip(trip({ trip_date: '2026-02-30' })), 'trip_date');
  rejects(() => svc.addTrip(trip({ vehicle_id: 'VEH-404404' })), 'vehicle_id');
  rejects(() => svc.addTrip(trip({ purpose_id: 'LKP-404404' })), 'purpose_id');
  rejects(() => svc.addTrip(trip({ destination: ' ' })), 'destination');
  rejects(() => svc.addTrip(trip({ end_km: 1012.4 })), 'end_km', /whole/);
});

test('distance is calculated for the list and never stored', () => {
  const { svc, repo, trip } = setup();
  const t = svc.addTrip(trip({ start_km: 1000, end_km: 1042 }));
  const listed = svc.listTrips().find((x) => x.id === t.id);
  assert.equal(listed.distance_km, 42);
  assert.equal(listed.vehicle_name, 'Test Bike');
  assert.equal(listed.purpose, 'Work');
  const stored = repo.get('trips', t.id);
  assert.ok(!('distance_km' in stored), 'distance must not be stored');
  assert.equal(distanceKm(stored), 42);
});

test('voiding a trip keeps it, marks it Voided and logs the change', () => {
  const { svc, repo, trip } = setup();
  const t = svc.addTrip(trip({ start_km: 1000, end_km: 1050 }));
  const v = svc.voidTrip(t.id);
  assert.equal(v.status, 'Voided');
  assert.equal(v.is_active, false);
  assert.ok(repo.get('trips', t.id), 'trip is never deleted');
  assert.equal(svc.listTrips().find((x) => x.id === t.id).status, 'Voided');
  const log = repo.auditLog().filter((r) => r.record_id === t.id).map((r) => r.action);
  assert.deepEqual(log, ['create', 'void']);
  assert.equal(svc.lastEndKm(trip().vehicle_id), 1000, 'voided trips do not count');
  rejects(() => svc.voidTrip(t.id), 'id', /already voided/);
});

test('a voided vehicle leaves the picker but keeps its trips', () => {
  const { svc, bike, trip } = setup();
  svc.addTrip(trip());
  svc.voidVehicle(bike.id);
  assert.equal(svc.listVehicles().length, 0);
  assert.equal(svc.listVehicles({ includeInactive: true }).length, 1);
  assert.equal(svc.listTrips().length, 1);
  rejects(() => svc.addTrip(trip({ start_km: 1012, end_km: 1020 })), 'vehicle_id');
});

test('trips are listed newest date first', () => {
  const { svc, trip } = setup();
  svc.addTrip(trip({ trip_date: '2026-01-05', start_km: 1000, end_km: 1010 }));
  svc.addTrip(trip({ trip_date: '2026-01-07', start_km: 1010, end_km: 1020 }));
  svc.addTrip(trip({ trip_date: '2026-01-06', start_km: 1020, end_km: 1030 }));
  assert.deepEqual(svc.listTrips().map((t) => t.trip_date), ['2026-01-07', '2026-01-06', '2026-01-05']);
});
