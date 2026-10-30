const test = require('node:test');
const assert = require('node:assert');
const { createMockTransport } = require('../src/repository/transport');
const { createRepository } = require('../src/repository/base');
const { createRepositories } = require('../src/repository');
const seed = require('./fixtures/seed.json');

const fixedNow = () => '2026-01-01T00:00:00.000Z';

test('insert generates ID keys and audit columns; get returns by ID', () => {
  const t = createMockTransport(seed);
  const repo = createRepository(t, 'teams', { now: fixedNow });
  const row = repo.insert('USR-0005', { name: 'Second Team' });
  assert.strictEqual(row.id, 'TEM-0002');
  assert.strictEqual(row.created_by, 'USR-0005');
  assert.strictEqual(row.created_at, fixedNow());
  assert.strictEqual(repo.get('TEM-0002').name, 'Second Team');
  assert.strictEqual(repo.get('TEM-9999'), null);
});

test('update changes values, stamps updated_*, and refuses id or audit edits', () => {
  const repo = createRepository(createMockTransport(seed), 'vehicles', { now: fixedNow });
  const row = repo.update('USR-0005', 'VEH-0001', { description: 'Renamed (fake)' });
  assert.strictEqual(row.description, 'Renamed (fake)');
  assert.strictEqual(row.updated_by, 'USR-0005');
  assert.throws(() => repo.update('USR-0005', 'VEH-0001', { id: 'VEH-0009' }), /cannot be edited/);
  assert.throws(() => repo.update('USR-0005', 'VEH-0001', { deleted_at: 'x' }), /cannot be edited/);
});

test('soft delete only sets deleted_at and keeps the row', () => {
  const t = createMockTransport(seed);
  const repo = createRepository(t, 'teams', { now: fixedNow });
  repo.softDelete('USR-0005', 'TEM-0001');
  assert.strictEqual(t.rowCount('teams'), 1);
  assert.strictEqual(repo.get('TEM-0001'), null);
  const kept = repo.get('TEM-0001', true);
  assert.strictEqual(kept.deleted_at, fixedNow());
  assert.strictEqual(kept.deleted_by, 'USR-0005');
  assert.deepStrictEqual(repo.list(), []);
  assert.throws(() => repo.softDelete('USR-0005', 'TEM-0001'), /not found/);
});

test('IDs are never reused after a soft delete', () => {
  const repo = createRepository(createMockTransport(seed), 'teams', { now: fixedNow });
  repo.softDelete('USR-0005', 'TEM-0001');
  assert.strictEqual(repo.insert('USR-0005', { name: 'B' }).id, 'TEM-0002');
});

test('list is paged and filters by value', () => {
  const repo = createRepository(createMockTransport(seed), 'users', { now: fixedNow });
  assert.strictEqual(repo.list({ limit: 2 }).length, 2);
  assert.strictEqual(repo.list({ offset: 3 }).length, 2);
  assert.deepStrictEqual(repo.list({ where: { role: 'driver' } }).map((r) => r.id), ['USR-0002']);
});

test('one value per cell: objects and unknown columns are refused', () => {
  const repo = createRepository(createMockTransport(seed), 'teams', { now: fixedNow });
  assert.throws(() => repo.insert('USR-0005', { name: ['a', 'b'] }), /one value per cell/);
  assert.throws(() => repo.insert('USR-0005', { nope: 'x' }), /unknown column/);
});

test('trip with travellers and readings saves and loads by ID', () => {
  const r = createRepositories(createMockTransport(seed), { now: fixedNow });
  const trip = r.trips.insert('USR-0001', {
    status: 'Draft', requestor_id: 'USR-0001', vehicle_id: 'VEH-0001', team_id: 'TEM-0001', purpose: 'Site visit (fake)',
  });
  const ttv = r.trip_travellers.insert('USR-0001', { trip_id: trip.id, user_id: 'USR-0002' });
  const odo = r.vehicle_readings.insert('USR-0001', { trip_id: trip.id, vehicle_id: 'VEH-0001', kind: 'start', reading: 1000 });
  assert.deepStrictEqual([trip.id, ttv.id, odo.id], ['TRP-0001', 'TTV-0001', 'ODO-0001']);
  assert.strictEqual(r.trips.get('TRP-0001').vehicle_id, 'VEH-0001');
  assert.strictEqual(r.trip_travellers.list({ where: { trip_id: trip.id } })[0].user_id, 'USR-0002');
  assert.strictEqual(r.vehicle_readings.get('ODO-0001').reading, 1000);
});
