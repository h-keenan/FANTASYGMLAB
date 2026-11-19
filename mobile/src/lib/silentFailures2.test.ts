import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { test } from 'node:test';

// Mobile has no RN render harness; source-level guards for the silent-failures follow-up (docs/audits/2026-11-silent-failures.md #5-8).
const read = (rel: string) => readFileSync(resolve(process.cwd(), 'src', rel), 'utf8');

test('Sim trade builder: a failed roster load shows a retry, not an empty builder', () => {
  const src = read('components/SimGameTrades.tsx');
  assert.match(src, /setRosterFailed\(true\)/);
  assert.match(src, /<ErrorState[^>]*SIM_LOAD_ERROR\.roster[^>]*onRetry=/);
  assert.doesNotMatch(src.replace(/\s+/g, ' '), /getSimGameTeam\([^)]*\)[^;]{0,260}\.catch\(\(\) => \{\}\)/);
});

test('Saved leagues, value signals and the share toggle surface failures', () => {
  assert.match(read('screens/MoreScreen.tsx'), /setSavedLeaguesFailed\(true\)/);
  assert.match(read('components/ValueSignalsCard.tsx'), /query\.isError/);
  assert.match(read('components/ShareToCommunityToggle.tsx'), /Could not stop sharing this trade/);
  assert.doesNotMatch(read('screens/TradeHistoryScreen.tsx'), /deleteSharedCommunityTrade\(id\)\.catch\(\(\) => \{\}\)/);
});
