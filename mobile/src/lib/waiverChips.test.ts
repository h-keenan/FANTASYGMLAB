import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { filterByRecommendation, waiverReasonChips } from './waiverChips.ts';

describe('waiverReasonChips', () => {
  it('maps real signals, catalysts first, capped at 2', () => {
    assert.deepEqual(
      waiverReasonChips({
        sleeper_trending_add: true,
        faab: { reasons: ['Fills a starting WR need for you', 'Usage up 40% lately', '3 teams need a WR'] },
      }),
      ['Trending', 'Usage +40%'],
    );
  });

  it('never invents a chip without a backing signal', () => {
    assert.deepEqual(waiverReasonChips({ faab: { reasons: ['Something else'] } }), []);
    assert.deepEqual(waiverReasonChips({}), []);
  });

  it('maps role, depth chart and injury cover', () => {
    assert.deepEqual(
      waiverReasonChips(
        { injury_replacement_fit: true, faab: { reasons: ['Moved up 2 spots on the depth chart', 'Role rising'] } },
        3,
      ),
      ['Role rising', 'Depth chart up', 'Injury cover'],
    );
  });
});

describe('bigger upgrade chip', () => {
  it('is one short line with the lineup gain, first, and absent without the server flag', () => {
    assert.deepEqual(waiverReasonChips({ bigger_upgrade: true, lineup_ppw: 1.84, sleeper_trending_add: true }), [
      'Bigger than your need: +1.8 pts/wk',
      'Trending',
    ]);
    assert.deepEqual(waiverReasonChips({ lineup_ppw: 1.84 }), []);
    assert.deepEqual(waiverReasonChips({ bigger_upgrade: true, lineup_ppw: null }), ['Bigger than your need']);
  });
});

describe('filterByRecommendation', () => {
  it('filters by recommendation label', () => {
    const rows = [{ recommendation_label: 'Add' }, { recommendation_label: 'Stash' }];
    assert.equal(filterByRecommendation(rows, 'Stash').length, 1);
    assert.equal(filterByRecommendation(rows, 'all').length, 2);
  });
});
