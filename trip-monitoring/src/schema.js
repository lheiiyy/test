// Schema version 1. A later change is a new version plus a migration with a rollback note.
const SCHEMA_VERSION = 1;
const AUDIT_COLUMNS = ['created_at', 'created_by', 'updated_at', 'updated_by', 'deleted_at', 'deleted_by'];

function table(sheet, prefix, columns) {
  return { sheet, prefix, columns: ['id'].concat(columns, AUDIT_COLUMNS) };
}

const TABLES = {
  users: table('users', 'USR', ['name', 'role', 'team_id']),
  teams: table('teams', 'TEM', ['name']),
  vehicles: table('vehicles', 'VEH', ['plate', 'description']),
  lookups: table('lookups', 'LKP', ['group', 'key', 'value']),
  audit_log: table('audit_log', 'AUD', ['at', 'actor_id', 'action', 'table', 'record_id', 'detail']),
  trips: table('trips', 'TRP', ['status', 'requestor_id', 'vehicle_id', 'team_id', 'purpose', 'note']),
  trip_travellers: table('trip_travellers', 'TTV', ['trip_id', 'user_id']),
  vehicle_readings: table('vehicle_readings', 'ODO', ['trip_id', 'vehicle_id', 'kind', 'reading']),
};

module.exports = { SCHEMA_VERSION, AUDIT_COLUMNS, TABLES };
