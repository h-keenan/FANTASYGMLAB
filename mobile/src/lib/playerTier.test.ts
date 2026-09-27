// Run with: node --experimental-strip-types --test src/lib/playerTier.test.ts
// (mobile has no jest/test runner configured yet — see backgroundRetry.test.ts
// for why plain Node's built-in test runner is used instead.)
import test from 'node:test';
import assert from 'node:assert/strict';

import { PLAYER_TIER_LADDER, resolvePlayerTier } from './playerTier.ts';

test('every tier has a distinct shortLabel and abbrLabel (no component should ever render the same word twice)', () => {
  for (const tier of PLAYER_TIER_LADDER) {
    assert.notEqual(
      tier.abbrLabel,
      tier.shortLabel,
      `${tier.tierId}: abbrLabel ("${tier.abbrLabel}") must differ from shortLabel ("${tier.shortLabel}")`,
    );
  }
});

test('elite and starter have real (non-duplicated) abbreviations', () => {
  const elite = PLAYER_TIER_LADDER.find((t) => t.tierId === 'elite');
  assert.equal(elite?.shortLabel, 'ELITE');
  assert.equal(elite?.abbrLabel, 'ELT');

  const starter = PLAYER_TIER_LADDER.find((t) => t.tierId === 'starter');
  assert.equal(starter?.shortLabel, 'STARTER');
  assert.equal(starter?.abbrLabel, 'STR');
});

test('resolvePlayerTier maps the legacy "star" stored value to the elite tier (its abbrLabel/shortLabel differ)', () => {
  // STORED_TIER_TO_ID intentionally maps legacy stored strings ("star",
  // "elite") onto today's ladder in a non-obvious way — "star" is what
  // resolves to the *elite* tierId; "elite" itself maps to "generational".
  const resolved = resolvePlayerTier('star');
  assert.equal(resolved.tierId, 'elite');
  assert.notEqual(resolved.abbrLabel, resolved.shortLabel);
});
