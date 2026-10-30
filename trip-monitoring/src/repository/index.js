const { TABLES } = require('../schema');
const { createRepository } = require('./base');

// One repository per table, keyed by table name (trips, trip_travellers, vehicle_readings, ...).
function createRepositories(transport, opts) {
  const repos = {};
  for (const name of Object.keys(TABLES)) repos[name] = createRepository(transport, name, opts);
  return repos;
}

module.exports = { createRepositories };
