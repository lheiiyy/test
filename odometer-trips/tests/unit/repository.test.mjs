import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRepository, memoryStorage, STORAGE_KEY } from '../../app/repository.js';

const AUDIT_COLUMNS = ['created_at', 'created_by', 'updated_at', 'updated_by', 'is_active', 'row_version'];

function setup() {
  const storage = memoryStorage();
  let tick = 0;
  const now = () => new Date(Date.UTC(2026, 0, 1, 0, 0, tick++));
  return { storage, now, repo: createRepository({ storage, now, user: 'tester' }) };
}

test('seeds the trip purposes Work, Personal and Other on first use', () => {
  const { repo } = setup();
  const values = repo.list('lookups').filter((r) => r.group_name === 'trip_purpose').map((r) => r.value);
  assert.deepEqual(values, ['Work', 'Personal', 'Other']);
});

test('insert gives a prefixed ID and all six audit columns', () => {
  const { repo } = setup();
  const v = repo.insert('vehicles', { name: 'Test Bike', plate: 'TEST-001', fuel_type: 'Gasoline', start_odometer_km: 1000 });
  assert.match(v.id, /^VEH-\d{6}$/);
  for (const col of AUDIT_COLUMNS) assert.ok(col in v, `missing ${col}`);
  assert.equal(v.is_active, true);
  assert.equal(v.row_version, 1);
  assert.equal(v.created_by, 'tester');
  const t = repo.insert('trips', { vehicle_id: v.id, trip_date: '2026-01-02', start_km: 1000, end_km: 1010 });
  assert.match(t.id, /^TRP-\d{6}$/);
});

test('callers cannot set the ID or audit columns', () => {
  const { repo } = setup();
  const v = repo.insert('vehicles', { id: 'VEH-999999', name: 'X', row_version: 7, is_active: false });
  assert.notEqual(v.id, 'VEH-999999');
  assert.equal(v.row_version, 1);
  assert.equal(v.is_active, true);
});

test('every change is written to the audit log', () => {
  const { repo } = setup();
  const before = repo.auditLog().length;
  const v = repo.insert('vehicles', { name: 'Test Bike' });
  repo.update('vehicles', v.id, { name: 'Test Bike 2' });
  repo.softDelete('vehicles', v.id);
  const rows = repo.auditLog().slice(before);
  assert.deepEqual(rows.map((r) => [r.table_name, r.record_id, r.action]), [
    ['vehicles', v.id, 'create'],
    ['vehicles', v.id, 'update'],
    ['vehicles', v.id, 'void'],
  ]);
  for (const r of rows) {
    assert.match(r.id, /^AUD-\d{6}$/);
    assert.ok(r.changed_at);
    for (const col of AUDIT_COLUMNS) assert.ok(col in r, `audit row missing ${col}`);
  }
});

test('update increments row_version and keeps created_* columns', () => {
  const { repo } = setup();
  const v = repo.insert('vehicles', { name: 'A' });
  const u = repo.update('vehicles', v.id, { name: 'B', created_by: 'hacker', id: 'VEH-000999' });
  assert.equal(u.id, v.id);
  assert.equal(u.name, 'B');
  assert.equal(u.row_version, 2);
  assert.equal(u.created_at, v.created_at);
  assert.equal(u.created_by, 'tester');
  assert.notEqual(u.updated_at, v.updated_at);
});

test('soft delete hides the row from list but never removes it', () => {
  const { repo } = setup();
  const v = repo.insert('vehicles', { name: 'A' });
  repo.softDelete('vehicles', v.id);
  assert.equal(repo.list('vehicles').length, 0);
  const all = repo.list('vehicles', { includeInactive: true });
  assert.equal(all.length, 1);
  assert.equal(all[0].is_active, false);
  assert.equal(repo.get('vehicles', v.id).is_active, false);
  assert.throws(() => repo.softDelete('vehicles', v.id), /already voided/);
});

test('the audit log cannot be written directly, and unknown tables are refused', () => {
  const { repo } = setup();
  assert.throws(() => repo.insert('audit_log', { action: 'x' }), /audit_log/);
  assert.throws(() => repo.insert('fuel_logs', {}), /Unknown table/);
  assert.throws(() => repo.update('vehicles', 'VEH-000404', {}), /not found/);
});

test('a second repository over the same storage returns the same rows', () => {
  const { repo, storage, now } = setup();
  const v = repo.insert('vehicles', { name: 'Test Bike', plate: 'TEST-001' });
  const again = createRepository({ storage, now, user: 'tester' });
  assert.deepEqual(again.list('vehicles'), repo.list('vehicles'));
  assert.deepEqual(again.get('vehicles', v.id), v);
  assert.equal(again.list('lookups').length, 3, 'purposes are not seeded twice');
  const v2 = again.insert('vehicles', { name: 'Next' });
  assert.notEqual(v2.id, v.id, 'ID sequence continues');
});

test('returned rows are copies, so callers cannot change stored data', () => {
  const { repo } = setup();
  const v = repo.insert('vehicles', { name: 'A' });
  v.name = 'changed';
  repo.list('vehicles')[0].name = 'changed';
  assert.equal(repo.get('vehicles', v.id).name, 'A');
});

test('corrupt storage is reported, not overwritten', () => {
  const storage = memoryStorage({ [STORAGE_KEY]: '{not json' });
  assert.throws(() => createRepository({ storage }), /corrupt/i);
  assert.equal(storage.getItem(STORAGE_KEY), '{not json');
});
