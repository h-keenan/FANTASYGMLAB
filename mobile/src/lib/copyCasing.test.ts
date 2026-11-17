import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';
import path from 'node:path';

// Runs in the mobile test job: keeps section/module headings from drifting in case between web and app.
test('headings do not differ in case between web and app (scripts/check_copy_casing.mjs)', () => {
  const script = path.resolve(process.cwd(), '../scripts/check_copy_casing.mjs');
  const result = spawnSync(process.execPath, [script], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr || result.stdout);
});
