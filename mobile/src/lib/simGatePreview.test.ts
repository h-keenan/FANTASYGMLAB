import assert from 'node:assert/strict';
import { test } from 'node:test';

import { simGamePaywalled, simGatePreview } from './simGame.ts';

test('a premium gate with no preview holds the paywalled one, never null (null means Pro)', () => {
  assert.equal(simGamePaywalled(simGatePreview({ preview: null })), true);
  assert.equal(simGamePaywalled(simGatePreview({})), true);
  const own = { free_season: true, weeks_left: 3, paywall_week: 18, paywalled: false };
  assert.equal(simGatePreview({ preview: own }), own);
});
