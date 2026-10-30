// CSV text builder: pure functions, no storage and no browser APIs.
// RFC 4180 quoting, CRLF line ends, a UTF-8 byte order mark so Excel reads it right,
// and an apostrophe in front of text that a spreadsheet could run as a formula.

export const BOM = '﻿';
const FORMULA_START = /^[=+\-@]/;

export function csvCell(value) {
  if (value === null || value === undefined) return '';
  let s = typeof value === 'string' ? value : String(value);
  if (typeof value === 'string' && FORMULA_START.test(s)) s = `'${s}`;
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function buildCsv(columns, rows) {
  const lines = [columns.map(csvCell).join(',')];
  for (const row of rows) lines.push(columns.map((c) => csvCell(row[c])).join(','));
  return BOM + lines.join('\r\n') + '\r\n';
}
