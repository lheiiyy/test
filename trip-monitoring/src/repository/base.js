const { TABLES, AUDIT_COLUMNS } = require('../schema');

const PAGE_SIZE = 50;

// Generic repository for one table. Rows are keyed by ID; delete is soft only.
function createRepository(transport, tableName, opts) {
  const def = TABLES[tableName];
  if (!def) throw new Error(`unknown table ${tableName}`);
  const now = (opts && opts.now) || (() => new Date().toISOString());

  function nextId() {
    const n = transport.rowCount(tableName) + 1; // soft-deleted rows stay, so IDs are never reused
    return `${def.prefix}-${String(n).padStart(4, '0')}`;
  }
  function strip(record) {
    return record && { ...record };
  }

  return {
    tableName,
    get(id, includeDeleted) {
      const hit = transport.findRow(tableName, 'id', id);
      if (!hit || (hit.record.deleted_at && !includeDeleted)) return null;
      return strip(hit.record);
    },
    list({ offset = 0, limit = PAGE_SIZE, where = {} } = {}) {
      const out = [];
      let pos = offset;
      while (out.length < limit) {
        const page = transport.readPage(tableName, pos, PAGE_SIZE);
        if (!page.length) break;
        for (const { record } of page) {
          if (record.deleted_at) continue;
          if (Object.entries(where).every(([k, v]) => record[k] === v)) out.push(strip(record));
          if (out.length === limit) break;
        }
        pos += page.length;
      }
      return out;
    },
    insert(actorId, values) {
      return transport.withLock(() => {
        const at = now();
        const record = { ...values, id: nextId(), created_at: at, created_by: actorId, updated_at: at, updated_by: actorId };
        transport.appendRow(tableName, record);
        return this.get(record.id);
      });
    },
    update(actorId, id, changes) {
      return transport.withLock(() => {
        const hit = transport.findRow(tableName, 'id', id);
        if (!hit || hit.record.deleted_at) throw new Error(`${tableName} ${id} not found`);
        for (const k of ['id'].concat(AUDIT_COLUMNS)) {
          if (k in changes) throw new Error(`${k} cannot be edited`);
        }
        const record = { ...hit.record, ...changes, updated_at: now(), updated_by: actorId };
        transport.updateRow(tableName, hit.rowIndex, record);
        return strip(record);
      });
    },
    softDelete(actorId, id) {
      return transport.withLock(() => {
        const hit = transport.findRow(tableName, 'id', id);
        if (!hit || hit.record.deleted_at) throw new Error(`${tableName} ${id} not found`);
        const at = now();
        const record = { ...hit.record, deleted_at: at, deleted_by: actorId, updated_at: at, updated_by: actorId };
        transport.updateRow(tableName, hit.rowIndex, record);
        return strip(record);
      });
    },
  };
}

module.exports = { createRepository, PAGE_SIZE };
