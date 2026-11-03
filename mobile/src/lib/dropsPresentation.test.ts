import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { limitedDataNote, lineupEffectText, needsHeadline, ordinal, teamNeedStat, valueEffectText } from './dropsPresentation.ts';

const effect = { lineup_points_ros: -3.4, lineup_points_per_week: -0.4, this_week: 0, value_delta: -412, score: -500, weeks: 9 };

describe('dropsPresentation', () => {
  it('formats ordinals', () => {
    assert.deepEqual([1, 2, 3, 4, 8, 11, 12, 13, 21, 22].map(ordinal), ['1st', '2nd', '3rd', '4th', '8th', '11th', '12th', '13th', '21st', '22nd']);
  });

  it('formats lineup and value effects, hiding noise', () => {
    assert.equal(lineupEffectText(effect), '-3 lineup pts over 9 weeks');
    assert.equal(lineupEffectText({ ...effect, lineup_points_ros: 0.2 }), 'No lineup change');
    assert.equal(valueEffectText(effect), 'Value -412');
    assert.equal(valueEffectText({ ...effect, value_delta: 40 }), '');
  });

  it("never answers 'None': Covered only from the model, an em dash when it failed", () => {
    assert.equal(teamNeedStat({ needs_model: null, needed_positions: [] }), '—');
    assert.equal(teamNeedStat({ needs_model: null, needed_positions: ['RB', 'QB'] }), 'RB/QB');
    assert.match(needsHeadline({ needs_model: null, needed_positions: [] }), /could not be fully modeled/);
  });

  it('builds the limited-data note from model_status', () => {
    assert.equal(limitedDataNote({ degraded: false, reasons: [] }), null);
    assert.equal(limitedDataNote({ degraded: true, reasons: [{ code: 'x', message: 'Lookup failed.' }] }), 'Limited data: Lookup failed.');
  });
});
