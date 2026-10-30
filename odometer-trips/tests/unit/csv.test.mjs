import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildCsv, csvCell, BOM } from '../../app/csv.js';

// Test-only RFC 4180 reader, used to prove the output reads back identical.
function parse(text) {
  const rows = [];
  let row = [];
  let cell = '';
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') { row.push(cell); cell = ''; }
    else if (ch === '\r' && text[i + 1] === '\n') { row.push(cell); rows.push(row); row = []; cell = ''; i++; }
    else cell += ch;
  }
  if (cell !== '' || row.length) { row.push(cell); rows.push(row); }
  return rows;
}

test('starts with a byte order mark, a header row and CRLF line ends', () => {
  const text = buildCsv(['id', 'name'], [{ id: 'VEH-000001', name: 'Test Bike' }]);
  assert.ok(text.startsWith(BOM));
  assert.equal(text.slice(1), 'id,name\r\nVEH-000001,Test Bike\r\n');
});

test('header only when there are no rows', () => {
  assert.equal(buildCsv(['a', 'b'], []).slice(1), 'a,b\r\n');
});

test('commas, quotes, line breaks, empty and non-ASCII values read back identical', () => {
  const values = ['a,b', 'say "hi"', 'line1\nline2', 'win\r\nbreak', '', 'Café 東京', '  padded  '];
  const rows = values.map((v, i) => ({ id: `R${i}`, text: v }));
  const parsed = parse(buildCsv(['id', 'text'], rows).slice(1));
  assert.deepEqual(parsed[0], ['id', 'text']);
  assert.deepEqual(parsed.slice(1).map((r) => r[1]), values);
  assert.equal(parsed.length, values.length + 1);
});

test('null, undefined, numbers and booleans', () => {
  assert.equal(csvCell(null), '');
  assert.equal(csvCell(undefined), '');
  assert.equal(csvCell(42), '42');
  assert.equal(csvCell(0), '0');
  assert.equal(csvCell(true), 'true');
  assert.equal(csvCell(false), 'false');
});

test('text starting with = + - or @ gets an apostrophe; numbers and other text do not', () => {
  assert.equal(csvCell('=SUM(A1)'), "'=SUM(A1)");
  assert.equal(csvCell('+1'), "'+1");
  assert.equal(csvCell('-x'), "'-x");
  assert.equal(csvCell('@cmd'), "'@cmd");
  assert.equal(csvCell(-5), '-5');
  assert.equal(csvCell('2026-02-01'), '2026-02-01');
  assert.equal(csvCell('a=b'), 'a=b');
  assert.equal(csvCell('=A,"B"'), '"\'=A,""B"""');
});

test('columns not present on a row are empty', () => {
  assert.equal(buildCsv(['a', 'b'], [{ a: 1 }]).slice(1), 'a,b\r\n1,\r\n');
});
