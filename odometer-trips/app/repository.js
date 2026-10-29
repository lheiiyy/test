// Repository: the only layer that reads or writes storage.
// Storage is any object with getItem/setItem (localStorage, sessionStorage or memoryStorage()).

export const STORAGE_KEY = 'odometer-trips:v1';

const PREFIX = { vehicles: 'VEH', trips: 'TRP', lookups: 'LKP', audit_log: 'AUD' };
const RESERVED = ['id', 'created_at', 'created_by', 'updated_at', 'updated_by', 'is_active', 'row_version'];
const TRIP_PURPOSES = ['Work', 'Personal', 'Other'];

export function memoryStorage(initial = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => { map.set(k, String(v)); },
    removeItem: (k) => { map.delete(k); },
  };
}

const copy = (row) => (row ? { ...row } : null);

function stripReserved(fields) {
  const out = { ...fields };
  for (const k of RESERVED) delete out[k];
  return out;
}

export function createRepository({ storage, user = 'leo', now = () => new Date(), key = STORAGE_KEY } = {}) {
  if (!storage) throw new Error('storage is required');

  function read() {
    const raw = storage.getItem(key);
    if (raw === null || raw === undefined) return null;
    try {
      return JSON.parse(raw);
    } catch {
      throw new Error(`Stored data under "${key}" is corrupt; it was left untouched.`);
    }
  }

  function write(db) {
    storage.setItem(key, JSON.stringify(db));
  }

  function checkTable(table) {
    if (!(table in PREFIX)) throw new Error(`Unknown table: ${table}`);
  }

  function nextId(db, table) {
    const prefix = PREFIX[table];
    db.seq[prefix] = (db.seq[prefix] || 0) + 1;
    return `${prefix}-${String(db.seq[prefix]).padStart(6, '0')}`;
  }

  function stamp() {
    return now().toISOString();
  }

  function addRow(db, table, fields) {
    const at = stamp();
    const row = {
      id: nextId(db, table),
      ...stripReserved(fields),
      created_at: at,
      created_by: user,
      updated_at: at,
      updated_by: user,
      is_active: true,
      row_version: 1,
    };
    db[table].push(row);
    return row;
  }

  function audit(db, table, recordId, action) {
    addRow(db, 'audit_log', { table_name: table, record_id: recordId, action, changed_at: stamp() });
  }

  function emptyDb() {
    const db = { schema_version: 1, seq: {} };
    for (const t of Object.keys(PREFIX)) db[t] = [];
    return db;
  }

  // Initialise once: create the store and seed trip purposes.
  if (read() === null) {
    const db = emptyDb();
    for (const value of TRIP_PURPOSES) {
      const row = addRow(db, 'lookups', { group_name: 'trip_purpose', value });
      audit(db, 'lookups', row.id, 'create');
    }
    write(db);
  }

  function load() {
    return read() ?? emptyDb();
  }

  function find(db, table, id) {
    const row = db[table].find((r) => r.id === id);
    if (!row) throw new Error(`${table} ${id} not found`);
    return row;
  }

  return {
    list(table, { includeInactive = false } = {}) {
      checkTable(table);
      return load()[table].filter((r) => includeInactive || r.is_active).map(copy);
    },

    get(table, id) {
      checkTable(table);
      return copy(load()[table].find((r) => r.id === id));
    },

    insert(table, fields) {
      checkTable(table);
      if (table === 'audit_log') throw new Error('audit_log is written by the repository only');
      const db = load();
      const row = addRow(db, table, fields);
      audit(db, table, row.id, 'create');
      write(db);
      return copy(row);
    },

    update(table, id, fields, { action = 'update' } = {}) {
      checkTable(table);
      if (table === 'audit_log') throw new Error('audit_log is written by the repository only');
      const db = load();
      const row = find(db, table, id);
      Object.assign(row, stripReserved(fields), {
        updated_at: stamp(),
        updated_by: user,
        row_version: row.row_version + 1,
      });
      if (action === 'void') row.is_active = false;
      audit(db, table, id, action);
      write(db);
      return copy(row);
    },

    softDelete(table, id, fields = {}) {
      checkTable(table);
      const existing = this.get(table, id);
      if (!existing) throw new Error(`${table} ${id} not found`);
      if (!existing.is_active) throw new Error(`${table} ${id} is already voided`);
      return this.update(table, id, fields, { action: 'void' });
    },

    auditLog() {
      return load().audit_log.map(copy);
    },
  };
}
