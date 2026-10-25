import assert from 'node:assert/strict';
import test from 'node:test';

import {
  radarPoints,
  rankLine,
  seasonStatGroups,
  tierOpportunityMismatchCaption,
} from './playerQuickViewPresentation.ts';

const item = (label: string) => ({ label, value: '1', note: '', percentile: null, tone: 'neutral' });

test('seasonStatGroups uses web order and skips empty groups', () => {
  const groups = seasonStatGroups({
    key_stats: [item('Rec')],
    fantasy: [item('PPR')],
    usage: [],
    efficiency: [item('YPRR')],
  });
  assert.deepEqual(groups.map((g) => g.title), ['Production', 'Fantasy', 'Efficiency']);
});

test('tier/opportunity mismatch only flags low tier with high opportunity', () => {
  assert.match(tierOpportunityMismatchCaption('Depth', 'Elite Opportunity') ?? '', /full season/);
  assert.equal(tierOpportunityMismatchCaption('Elite', 'Elite Opportunity'), null);
  assert.equal(tierOpportunityMismatchCaption('Depth', null), null);
  assert.equal(tierOpportunityMismatchCaption(null, 'Elite Opportunity'), null);
});

test('rankLine formats overall and position ranks, null when unknown', () => {
  assert.equal(rankLine('WR', 12, 4), 'Overall #12 · WR #4');
  assert.equal(rankLine('WR', null, 4), 'WR #4');
  assert.equal(rankLine(null, null, 4), 'Position #4');
  assert.equal(rankLine('WR', null, null), null);
});

test('radarPoints requires every axis and clamps to 0-99', () => {
  const full = [
    { label: 'MKT', rating: 90 },
    { label: 'OPP', rating: 120 },
    { label: 'SCR', rating: 50 },
  ];
  assert.deepEqual(radarPoints(full)?.map((p) => p.value), [90, 99, 50]);
  assert.equal(radarPoints([...full, { label: 'DUR', rating: null }]), null);
  assert.equal(radarPoints(full.slice(0, 2)), null);
});
