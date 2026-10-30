// Transport interface (the real Sheets one is a later manual step):
//   rowCount(sheet) / readPage(sheet, offset, limit) / findRow(sheet, column, value)
//   appendRow(sheet, record) / updateRow(sheet, rowIndex, record) / withLock(fn)
// The mock keeps "sheets" in memory; rows are plain objects, one scalar per cell.
const { TABLES } = require('../schema');

function createMockTransport(seed) {
  const sheets = {};
  for (const name of Object.keys(TABLES)) sheets[name] = [];
  for (const [name, rows] of Object.entries(seed || {})) {
    for (const r of rows) sheets[name].push(Object.assign(blank(name), r));
  }

  function blank(name) {
    const row = {};
    for (const c of TABLES[name].columns) row[c] = null;
    return row;
  }
  function sheet(name) {
    if (!sheets[name]) throw new Error(`unknown sheet ${name}`);
    return sheets[name];
  }
  function checkCells(name, record) {
    for (const [k, v] of Object.entries(record)) {
      if (!TABLES[name].columns.includes(k)) throw new Error(`unknown column ${name}.${k}`);
      if (v !== null && !['string', 'number'].includes(typeof v)) {
        throw new Error(`${name}.${k} must hold one value per cell`);
      }
    }
  }

  return {
    rowCount: (name) => sheet(name).length,
    readPage: (name, offset, limit) =>
      sheet(name).slice(offset, offset + limit).map((r, i) => ({ rowIndex: offset + i, record: { ...r } })),
    findRow(name, column, value) {
      const i = sheet(name).findIndex((r) => r[column] === value);
      return i < 0 ? null : { rowIndex: i, record: { ...sheet(name)[i] } };
    },
    appendRow(name, record) {
      checkCells(name, record);
      sheet(name).push(Object.assign(blank(name), record));
      return sheet(name).length - 1;
    },
    updateRow(name, rowIndex, record) {
      checkCells(name, record);
      if (!sheet(name)[rowIndex]) throw new Error(`no row ${rowIndex} in ${name}`);
      sheet(name)[rowIndex] = Object.assign(blank(name), record);
    },
    // Single writer: the mock is synchronous, so a plain call is already exclusive.
    // The Sheets transport maps this to LockService; a lock timeout throws and the write is not made.
    withLock: (fn) => fn(),
  };
}

module.exports = { createMockTransport };
