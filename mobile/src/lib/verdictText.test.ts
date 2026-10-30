import assert from 'node:assert/strict';
import { test } from 'node:test';

import { dropRepeatedSentences, shortSummary } from './verdictText.ts';

const lineup = 'This costs you about 12.4 pts/week in your starting lineup.';

test('drops sentences already shown', () => {
  assert.equal(
    dropRepeatedSentences(`${lineup} Your side gives up more value.`, [lineup]),
    'Your side gives up more value.',
  );
  assert.equal(dropRepeatedSentences(lineup.toUpperCase(), [lineup]), '');
});

test('summarises to first sentence', () => {
  assert.equal(shortSummary(`${lineup} More.`), lineup);
  assert.equal(shortSummary('', 2), '');
});
