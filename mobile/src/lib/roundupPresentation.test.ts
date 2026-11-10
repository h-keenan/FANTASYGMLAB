// Run with: node --experimental-strip-types --test src/lib/roundupPresentation.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  PREDICTABILITY_LABEL,
  formatPoints,
  predictabilityToken,
  regretBarPercent,
  roundupReasonMessage,
  roundupWeeks,
  swapLine,
} from './roundupPresentation.ts';

test('formats points and swap lines', () => {
  assert.equal(formatPoints(3), '3.0');
  assert.equal(formatPoints(null), '0.0');
  assert.equal(
    swapLine({ started: { name: 'Alpha', points: 3 }, benched: { name: 'Beta', points: 21.04 } }),
    'Alpha (3.0) over Beta (21.0)',
  );
});

test('each predictability tag has its own label and semantic token', () => {
  const tags = ['foreseeable', 'coin_flip', 'unforeseeable'] as const;
  assert.equal(new Set(tags.map(predictabilityToken)).size, 3);
  assert.deepEqual(tags.map((t) => PREDICTABILITY_LABEL[t]), ['Foreseeable', 'Coin flip', 'Unforeseeable']);
});

test('reasons degrade to specific copy with a generic fallback', () => {
  assert.equal(roundupReasonMessage('no_completed_week').title, 'No roundup yet');
  assert.match(roundupReasonMessage('unsupported_platform').subtitle, /ESPN/);
  assert.equal(roundupReasonMessage('mystery').title, 'Roundup is not ready');
});

test('week lists and regret bars', () => {
  assert.deepEqual(roundupWeeks(3), [1, 2, 3]);
  assert.deepEqual(roundupWeeks(0), []);
  assert.equal(regretBarPercent(10, 20), 50);
  assert.equal(regretBarPercent(0, 20), 0);
  assert.equal(regretBarPercent(0.1, 100), 4);
});

test('web twin has the same copy and tag labels', () => {
  const here = dirname(fileURLToPath(import.meta.url));
  const web = readFileSync(join(here, '..', '..', '..', 'web-next', 'src', 'lib', 'roundupPresentation.ts'), 'utf8');
  for (const label of Object.values(PREDICTABILITY_LABEL)) assert.ok(web.includes(`"${label}"`), label);
  for (const reason of ['no_completed_week', 'unsupported_platform', 'no_sleeper_username_linked']) {
    const { title, subtitle } = roundupReasonMessage(reason);
    assert.ok(web.includes(title.replace(/'/g, "\\'")) || web.includes(title), title);
    assert.ok(web.includes(subtitle), subtitle);
  }
});
