import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { describe, it } from 'node:test';

// Motion guard (rules and allowlist: scripts/check_motion_usage.mjs, which scans web-next/ and mobile/).
describe('motion scan', () => {
  it('finds no new layout-property transitions or non-native-driver animations', () => {
    const script = path.resolve(import.meta.dirname, '../../../scripts/check_motion_usage.mjs');
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
