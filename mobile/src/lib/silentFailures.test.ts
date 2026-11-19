import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { test } from 'node:test';

// Mobile has no RN render harness; these guard the silent-failure fixes (docs/audits/2026-11-silent-failures.md) at source level.
const read = (rel: string) => readFileSync(resolve(process.cwd(), 'src/components', rel), 'utf8');

test('SimRealHistory: errors offer a retry and a failed game log is not read as "no games"', () => {
  const src = read('SimRealHistory.tsx');
  assert.match(src, /<ErrorState[^>]*onRetry=\{retry\}/);
  assert.match(src, /stats_available === false/);
  assert.doesNotMatch(src, /setLog\(\[\]\)/);
});

test('PortfolioFreeStanding: a failed standing load shows a retry, not nothing', () => {
  const src = read('PortfolioFreeStanding.tsx');
  assert.match(src, /setFailed\(true\)/);
  assert.match(src, /<ErrorState compact[^>]*onRetry=/);
  assert.doesNotMatch(src, /\.catch\(\(\) => \{\}\)/);
});
