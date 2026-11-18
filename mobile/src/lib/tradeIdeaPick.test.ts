// Run with: node --experimental-strip-types --test src/lib/tradeIdeaPick.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { partnerFitLine, pickProjectionLine } from './tradeIdeaPick.ts';

test('shows the projected slot and whose pick it is', () => {
  assert.equal(pickProjectionLine({ projected_slot_label: '1.04', original_team_name: 'Gridiron', owner_team_name: 'Me' }), "proj. 1.04 · Gridiron's pick");
});

test("drops the owner part for the holder's own pick and falls back to the range", () => {
  assert.equal(pickProjectionLine({ projected_slot_label: '1.04', original_team_name: 'Me', owner_team_name: 'Me' }), 'proj. 1.04');
  assert.equal(pickProjectionLine({ projected_range: 'Early 1st' }), 'proj. Early 1st');
  assert.equal(pickProjectionLine({}), null);
});

test('partner fit line passes through, empty is null', () => {
  assert.equal(partnerFitLine(" Fills their TE hole · they're contending "), "Fills their TE hole · they're contending");
  assert.equal(partnerFitLine(''), null);
  assert.equal(partnerFitLine(undefined), null);
});
