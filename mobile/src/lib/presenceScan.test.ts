// Run with: node --experimental-strip-types --test src/lib/presenceScan.test.ts
// Runs the repo-level guard (scripts/check_presence_usage.mjs, also run by web-next's presenceScan.test.ts): no NEW hand-rolled
// expander body (`{open ? (<View>) : null}`) or stray LayoutAnimation outside the shared Presence module and its allowlist.
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import path from 'node:path';

test('no hand-rolled expand/collapse outside the Presence allowlist', () => {
  const script = path.resolve(process.cwd(), '../scripts/check_presence_usage.mjs');
  let output = '';
  try {
    output = execFileSync('node', [script], { encoding: 'utf8', stdio: 'pipe' });
  } catch (error) {
    const failure = error as { stderr?: string; stdout?: string };
    throw new Error(failure.stderr || failure.stdout || String(error));
  }
  assert.ok(output.includes('passed'));
});
