const { TABLES } = require('../schema');
const { createRepository } = require('./base');

// One repository per table, keyed by table name (trips, trip_travellers, vehicle_readings, ...).
function createRepositories(transport, opts) {
  const repos = {};
  // The same clock the repositories stamp rows with, so services can reuse it.
  Object.defineProperty(repos, 'now', { value: (opts && opts.now) || (() => new Date().toISOString()) });
  for (const name of Object.keys(TABLES)) repos[name] = createRepository(transport, name, opts);
  return repos;
}

module.exports = { createRepositories };
