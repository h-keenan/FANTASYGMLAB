import test from 'node:test';
import assert from 'node:assert/strict';

import { ACCENT_BY_DESTINATION, accentFor, destinationId } from './destinationAccents.generated.ts';
import { accentColor, type AccentPalette } from './destinationAccent.ts';
import { FEATURE_ITEMS } from './featureCatalog.ts';

const palette: AccentPalette = {
  accent: 'A', success: 'S', warning: 'W', danger: 'D', opportunity: 'O', violet: 'V', premium: 'P',
};

test('every feature-catalog item has an accent and uses the shared one', () => {
  for (const item of FEATURE_ITEMS) {
    assert.ok(ACCENT_BY_DESTINATION[item.id], `${item.id} has an accent`);
    assert.equal(item.color, ACCENT_BY_DESTINATION[item.id], item.id);
  }
  for (const id of Object.keys(ACCENT_BY_DESTINATION)) {
    assert.ok(FEATURE_ITEMS.some((i) => i.id === id), `${id} is a catalog id`);
  }
});

test('nav labels resolve to catalog ids', () => {
  assert.equal(destinationId('My Team'), 'my-team');
  assert.equal(accentFor('League Recaps'), 'information');
  assert.equal(accentFor('Home'), 'accent');
});

test('semantic tokens resolve to the web-equivalent theme colors', () => {
  // The 12 destinations that used to differ from web (audit 2026-11).
  const expected: Record<string, string> = {
    Alerts: 'W', Matchup: 'D', Waivers: 'O', Players: 'V', 'Trade Hub': 'A', 'GM Plan': 'S',
    'Draft Center': 'D', 'Live Draft': 'D', Games: 'O', 'League Recaps': 'A', News: 'A', Portfolio: 'P', 'Trade History': 'V',
  };
  for (const [label, color] of Object.entries(expected)) assert.equal(accentColor(palette, label), color, label);
});
