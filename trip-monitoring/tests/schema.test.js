const test = require('node:test');
const assert = require('node:assert');
const { TABLES, AUDIT_COLUMNS } = require('../src/schema');
const seed = require('./fixtures/seed.json');

test('every table has an ID key with a prefix and the six audit columns', () => {
  const names = ['users', 'teams', 'vehicles', 'lookups', 'audit_log', 'trips', 'trip_travellers', 'vehicle_readings'];
  assert.deepStrictEqual(Object.keys(TABLES).sort(), names.sort());
  assert.strictEqual(AUDIT_COLUMNS.length, 6);
  for (const t of Object.values(TABLES)) {
    assert.strictEqual(t.columns[0], 'id');
    assert.match(t.prefix, /^[A-Z]{3}$/);
    for (const c of AUDIT_COLUMNS) assert.ok(t.columns.includes(c), `${t.sheet} lacks ${c}`);
  }
});

test('trip tables use the TRP, TTV and ODO prefixes', () => {
  assert.strictEqual(TABLES.trips.prefix, 'TRP');
  assert.strictEqual(TABLES.trip_travellers.prefix, 'TTV');
  assert.strictEqual(TABLES.vehicle_readings.prefix, 'ODO');
});

test('fixtures only use known columns and one scalar value per cell', () => {
  for (const [sheet, rows] of Object.entries(seed)) {
    assert.ok(TABLES[sheet], `unknown table ${sheet}`);
    for (const row of rows) {
      for (const [k, v] of Object.entries(row)) {
        assert.ok(TABLES[sheet].columns.includes(k), `${sheet}.${k}`);
        assert.ok(v === null || ['string', 'number'].includes(typeof v), `${sheet}.${k} not scalar`);
      }
    }
  }
});
