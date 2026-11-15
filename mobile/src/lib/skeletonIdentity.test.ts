import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { describe, it } from 'node:test';

// Loading identity guard (rules and allowlist: scripts/check_skeleton_identity.mjs, which scans web-next/ and mobile/).
describe('loading identity scan', () => {
  it('finds no bare loading text or spinner-only screens outside the skeleton module', () => {
    const script = path.resolve(import.meta.dirname, '../../../scripts/check_skeleton_identity.mjs');
    let output = '';
    try {
      output = execFileSync('node', [script], { encoding: 'utf8', stdio: 'pipe' });
    } catch (error) {
      const failure = error as { stderr?: string; stdout?: string };
      throw new Error(failure.stderr || failure.stdout || String(error));
    }
    assert.ok(output.includes('passed'));
  });
});
