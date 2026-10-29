import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const readmePath = fileURLToPath(new URL('../README.md', import.meta.url));

test('README exists', () => {
  assert.ok(existsSync(readmePath), 'odometer-trips/README.md is missing');
});

test('first line is the title', () => {
  const lines = readFileSync(readmePath, 'utf8').split(/\r?\n/);
  assert.equal(lines[0], '# Odometer Trip Log');
});

test('exactly one sentence follows the title and mentions odometer', () => {
  const body = readFileSync(readmePath, 'utf8').split(/\r?\n/).slice(1).filter((l) => l.trim() !== '');
  assert.equal(body.length, 1, 'expected exactly one non-empty line after the title');
  const sentence = body[0].trim();
  assert.match(sentence, /^[^.!?]+\.$/, 'expected a single sentence ending with a full stop');
  assert.match(sentence, /odometer/i);
});
