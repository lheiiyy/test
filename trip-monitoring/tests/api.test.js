const test = require('node:test');
const assert = require('node:assert');
const { createApi } = require('../src/api');
const seed = require('./fixtures/seed.json');

const NOW = () => '2026-01-01T00:00:00.000Z';
const as = (api, id) => { assert.ok(api.setUser(id).ok); return api; };
const mk = () => createApi('mock', { seed, now: NOW });
const input = { vehicle_id: 'VEH-0001', team_id: 'TEM-0001', purpose: 'Site visit (fake)' };

test('only the mock transport exists, and it needs a seed', () => {
  assert.throws(() => createApi('rest', { seed }), /not available/);
  assert.throws(() => createApi('mock'), /needs a seed/);
});

test('calls without a user are refused in the error shape', () => {
  assert.deepStrictEqual(mk().listTrips(), { ok: false, error: 'no user selected' });
  assert.strictEqual(mk().setUser('USR-9999').ok, false);
});

test('users() lists the seed users for the role switcher', () => {
  const roles = mk().users().map((u) => u.role);
  assert.deepStrictEqual(roles, ['requestor', 'driver', 'supervisor', 'accounting', 'admin']);
});

test('each action succeeds for its role through the whole flow', () => {
  const api = mk();
  const t = as(api, 'USR-0001').createTrip(input).data;
  assert.ok(api.updateTrip(t.id, { purpose: 'Edited (fake)' }).ok);
  assert.ok(api.addTraveller(t.id, 'USR-0002').ok);
  assert.ok(api.recordReading(t.id, 'start', 100).ok);
  assert.ok(api.recordReading(t.id, 'end', 150).ok);
  assert.strictEqual(api.getTrip(t.id).data.readings.length, 2);
  assert.strictEqual(api.submit(t.id).data.status, 'Submitted');
  assert.strictEqual(as(api, 'USR-0003').validate(t.id).data.status, 'Trip validated');
  assert.strictEqual(as(api, 'USR-0004').complete(t.id).data.status, 'Completed');
  assert.strictEqual(api.listTrips({ status: 'Completed' }).data.length, 1);
});

test('returnToDraft needs a supervisor and a reason', () => {
  const api = mk();
  const t = as(api, 'USR-0002').createTrip(input).data;
  api.addTraveller(t.id, 'USR-0001');
  api.submit(t.id);
  assert.match(as(api, 'USR-0003').returnToDraft(t.id, '').error, /reason is required/);
  assert.strictEqual(api.returnToDraft(t.id, 'Fix purpose').data.status, 'Draft');
});

test('actions are refused for the wrong role', () => {
  const api = mk();
  const t = as(api, 'USR-0001').createTrip(input).data;
  api.addTraveller(t.id, 'USR-0002');
  api.submit(t.id);
  assert.match(as(api, 'USR-0001').validate(t.id).error, /not allowed/);
  assert.match(api.complete(t.id).error, /not allowed/);
  assert.match(as(api, 'USR-0003').createTrip(input).error, /not allowed/);
  assert.match(as(api, 'USR-0004').validate(t.id).error, /not allowed/);
  assert.match(as(api, 'USR-0002').getTrip(t.id).error, /may not view/);
});

test('mock state is per api instance', () => {
  const a = as(mk(), 'USR-0001');
  a.createTrip(input);
  assert.strictEqual(as(mk(), 'USR-0001').listTrips().data.length, 0);
});

test('web seed matches the dummy fixture', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const src = fs.readFileSync(path.join(__dirname, '../src/web/seed.js'), 'utf8');
  const win = {};
  new Function('window', src)(win);
  assert.deepStrictEqual(win.TM_SEED, seed);
});

test('exportState carries the mock state into a new api through its seed', () => {
  const a = as(mk(), 'USR-0001');
  const t = a.createTrip(input).data;
  const b = createApi('mock', { seed: a.exportState(), userId: 'USR-0003', now: NOW });
  assert.strictEqual(b.getTrip(t.id).data.purpose, input.purpose);
});
