import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { test } from 'node:test';

import { VERDICT_FEEDBACK_REASONS, VERDICT_TRUST_COPY } from './verdictTrust.ts';

function shared(path: string): string {
  const text = readFileSync(resolve(process.cwd(), path), 'utf8');
  const start = text.indexOf('// SHARED BEGIN');
  const end = text.indexOf('// SHARED END');
  assert.ok(start >= 0 && end > start, `${path} missing SHARED markers`);
  return text.slice(start, end);
}

test('web and app share one verdict trust block', () => {
  assert.equal(shared('src/lib/verdictTrust.ts'), shared('../web-next/src/lib/verdictTrust.ts'));
});

test('reasons are the fixed server list (no free text) and the copy promises no personal details', () => {
  assert.deepEqual(
    VERDICT_FEEDBACK_REASONS.map((r) => r.key),
    ['lineup_wrong', 'injury_wrong', 'values_off', 'partner_wouldnt', 'other'],
  );
  assert.match(VERDICT_TRUST_COPY.thanks, /No personal details/);
});
