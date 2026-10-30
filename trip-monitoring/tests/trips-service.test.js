const test = require('node:test');
const assert = require('node:assert');
const { createMockTransport } = require('../src/repository/transport');
const { createRepositories } = require('../src/repository');
const { createTripService, TRANSITIONS } = require('../src/services/trips');
const seed = require('./fixtures/seed.json');

const REQ = 'USR-0001', SUP = 'USR-0003', ACC = 'USR-0004', ADM = 'USR-0005';

function setup() {
  const repos = createRepositories(createMockTransport(seed), { now: () => '2026-01-01T00:00:00.000Z' });
  return { repos, svc: createTripService(repos) };
}
const draft = (svc) =>
  svc.createTrip(REQ, { vehicle_id: 'VEH-0001', team_id: 'TEM-0001', purpose: 'Site visit (fake)' });

test('createTrip makes a Draft owned by the requestor', () => {
  const { svc } = setup();
  const t = draft(svc);
  assert.strictEqual(t.status, 'Draft');
  assert.strictEqual(t.requestor_id, REQ);
});

test('legal transitions pass through the whole flow', () => {
  const { svc } = setup();
  const t = draft(svc);
  svc.addTraveller(REQ, t.id, 'USR-0002');
  assert.strictEqual(svc.submit(REQ, t.id).status, 'Submitted');
  assert.strictEqual(svc.validate(SUP, t.id).status, 'Trip validated');
  assert.throws(() => svc.complete(ACC, t.id), /start and end/);
  svc.returnToDraft(SUP, t.id, 'Add readings');
  svc.recordReading(REQ, t.id, 'start', 1000);
  svc.recordReading(REQ, t.id, 'end', 1050);
  svc.submit(REQ, t.id);
  svc.validate(SUP, t.id);
  assert.strictEqual(svc.complete(ACC, t.id).status, 'Completed');
});

test('illegal transitions fail', () => {
  const { svc } = setup();
  const t = draft(svc);
  assert.throws(() => svc.validate(SUP, t.id), /Draft to Trip validated/);
  assert.throws(() => svc.complete(ACC, t.id), /Draft to Completed/);
  svc.submit(REQ, t.id);
  assert.throws(() => svc.submit(REQ, t.id), /Submitted to Submitted/);
  assert.ok(!TRANSITIONS.Completed.length);
});

test('return to Draft works from Submitted and Trip validated, with a reason', () => {
  const { svc } = setup();
  const t = draft(svc);
  svc.addTraveller(REQ, t.id, 'USR-0002');
  svc.submit(REQ, t.id);
  assert.throws(() => svc.returnToDraft(SUP, t.id, ''), /reason/);
  const back = svc.returnToDraft(SUP, t.id, 'Wrong vehicle');
  assert.strictEqual(back.status, 'Draft');
  assert.strictEqual(back.note, 'Wrong vehicle');
  svc.submit(REQ, t.id);
  svc.validate(SUP, t.id);
  assert.strictEqual(svc.returnToDraft(SUP, t.id, 'Odometer typo').status, 'Draft');
});

test('validation rules: required fields, vehicle, travellers, readings', () => {
  const { svc } = setup();
  assert.throws(() => svc.createTrip(REQ, { vehicle_id: 'VEH-0001', team_id: 'TEM-0001' }), /purpose/);
  assert.throws(() => svc.createTrip(REQ, { vehicle_id: 'VEH-9999', team_id: 'TEM-0001', purpose: 'x' }), /vehicle/);
  const t = draft(svc);
  svc.submit(REQ, t.id);
  assert.throws(() => svc.validate(SUP, t.id), /traveller/);
  svc.returnToDraft(SUP, t.id, 'Add travellers');
  svc.addTraveller(REQ, t.id, 'USR-0002');
  svc.submit(REQ, t.id);
  svc.validate(SUP, t.id);
  assert.throws(() => svc.complete(ACC, t.id), /start and end/);
  svc.returnToDraft(SUP, t.id, 'Add readings');
  svc.recordReading(REQ, t.id, 'start', 500);
  svc.recordReading(REQ, t.id, 'end', 400);
  assert.throws(() => svc.recordReading(REQ, t.id, 'middle', 1), /kind/);
  svc.submit(REQ, t.id);
  svc.validate(SUP, t.id);
  assert.throws(() => svc.complete(ACC, t.id), /end reading/);
});

test('wrong role is refused, and nothing is written', () => {
  const { svc, repos } = setup();
  const t = draft(svc);
  svc.addTraveller(REQ, t.id, 'USR-0002');
  assert.throws(() => svc.submit(SUP, t.id), /not allowed/);
  svc.submit(REQ, t.id);
  assert.throws(() => svc.validate(REQ, t.id), /not allowed/);
  assert.throws(() => svc.validate('USR-0099', t.id), /unknown user/);
  assert.strictEqual(repos.trips.get(t.id).status, 'Submitted');
  svc.validate(SUP, t.id);
  assert.throws(() => svc.complete(SUP, t.id), /not allowed/);
  assert.strictEqual(repos.trips.get(t.id).status, 'Trip validated');
});

test('only the requestor or an admin may change a trip they own', () => {
  const { svc } = setup();
  const t = draft(svc);
  assert.throws(() => svc.submit('USR-0002', t.id), /own trips/);
  assert.strictEqual(svc.addTraveller(ADM, t.id, 'USR-0002').trip_id, t.id);
});

test('every write adds an audit row; failed calls add none', () => {
  const { svc, repos } = setup();
  const t = draft(svc);
  svc.addTraveller(REQ, t.id, 'USR-0002');
  svc.submit(REQ, t.id);
  const rows = repos.audit_log.list();
  assert.deepStrictEqual(rows.map((r) => r.action), ['create', 'add_traveller', 'submit']);
  assert.strictEqual(rows[0].actor_id, REQ);
  assert.strictEqual(rows[0].table, 'trips');
  assert.strictEqual(rows[0].record_id, t.id);
  assert.throws(() => svc.validate(REQ, t.id));
  assert.strictEqual(repos.audit_log.list().length, 3);
});

test('delete is soft, audited and role checked', () => {
  const { svc, repos } = setup();
  const t = draft(svc);
  assert.throws(() => svc.deleteTrip(ACC, t.id), /not allowed/);
  svc.deleteTrip(REQ, t.id);
  assert.strictEqual(repos.trips.get(t.id), null);
  assert.ok(repos.trips.get(t.id, true).deleted_at);
  assert.strictEqual(repos.audit_log.list().pop().action, 'delete');
});

test('readings only while Draft, and only one start and one end', () => {
  const { svc } = setup();
  const t = draft(svc);
  svc.recordReading(REQ, t.id, 'start', 1000);
  assert.throws(() => svc.recordReading(REQ, t.id, 'start', 1001), /already exists/);
  svc.addTraveller(REQ, t.id, 'USR-0002');
  svc.submit(REQ, t.id);
  assert.throws(() => svc.recordReading(REQ, t.id, 'end', 1050), /only change while the trip is Draft/);
});

test('only a Draft trip can be deleted', () => {
  const { svc, repos } = setup();
  const t = draft(svc);
  svc.addTraveller(REQ, t.id, 'USR-0002');
  svc.submit(REQ, t.id);
  assert.throws(() => svc.deleteTrip(REQ, t.id), /only a Draft/);
  assert.ok(repos.trips.get(t.id));
});

test('audit rows use the injected clock', () => {
  const { svc, repos } = setup();
  draft(svc);
  assert.strictEqual(repos.audit_log.list()[0].at, '2026-01-01T00:00:00.000Z');
});
