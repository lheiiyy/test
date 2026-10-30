// Client the screens call: screens -> api.js -> services -> repository -> transport.
// Every call returns {ok: true, data} or {ok: false, error}, so a REST transport can replace `mock`
// without any screen change. Only the `mock` transport exists in M1.
const { createMockTransport } = require('./repository/transport');
const { createRepositories } = require('./repository');
const { createTripService } = require('./services/trips');

const ACTIONS = [
  'listTrips', 'getTrip', 'lookups', 'createTrip', 'updateTrip', 'addTraveller',
  'recordReading', 'submit', 'validate', 'complete', 'returnToDraft', 'deleteTrip',
];

function createApi(transportName, opts) {
  if (transportName !== 'mock') throw new Error(`transport ${transportName} is not available yet`);
  const o = opts || {};
  if (!o.seed) throw new Error('the mock transport needs a seed');
  const repos = createRepositories(createMockTransport(o.seed), { now: o.now });
  const svc = createTripService(repos);
  let userId = o.userId || null;

  const api = {
    transport: 'mock',
    // The role switcher for the mock user: seed users only, no sign-in.
    users: () => repos.users.list().map((u) => ({ id: u.id, name: u.name, role: u.role })),
    setUser(id) {
      if (!repos.users.get(id)) return { ok: false, error: `unknown user ${id}` };
      userId = id;
      return { ok: true, data: repos.users.get(id) };
    },
    currentUser: () => (userId ? repos.users.get(userId) : null),
  };
  for (const name of ACTIONS) {
    api[name] = (...args) => {
      try {
        if (!userId) throw new Error('no user selected');
        return { ok: true, data: svc[name](userId, ...args) };
      } catch (e) {
        return { ok: false, error: e.message };
      }
    };
  }
  return api;
}

module.exports = { createApi, ACTIONS };
