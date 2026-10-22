import assert from 'node:assert/strict';
import test from 'node:test';

import { buildRosterComposition, buildTeamAnalysisRows } from './myTeamAnalysis.ts';

test('composition splits value by group, drops empty groups and sums to 100', () => {
  const segments = buildRosterComposition([
    { key: 'starters', label: 'Starters', players: [{ score: 1000 }, { score: 1000 }] },
    { key: 'bench', label: 'Bench', players: [{ score: 1000 }] },
    { key: 'ir', label: 'IR', players: [{ score: 1000 }] },
    { key: 'taxi', label: 'Taxi', players: [] },
  ]);
  assert.deepEqual(segments.map((s) => s.key), ['starters', 'bench', 'ir']);
  assert.deepEqual(segments.map((s) => s.percent), [50, 25, 25]);
  const thirds = buildRosterComposition([
    { key: 'a', label: 'A', players: [{ score: 1 }] },
    { key: 'b', label: 'B', players: [{ score: 1 }] },
    { key: 'c', label: 'C', players: [{ score: 1 }] },
  ]);
  assert.equal(thirds.reduce((sum, s) => sum + s.percent, 0), 100);
});

test('composition is empty when nothing has value', () => {
  assert.deepEqual(buildRosterComposition([{ key: 's', label: 'S', players: [{ score: null }] }]), []);
});

test('analysis rows are ordered QB/RB/WR/TE and carry short statuses', () => {
  const group = (position: string, over: object = {}) => ({
    position,
    classification: 'covered',
    reasons: [`${position} body`],
    upgrade_opportunity: false,
    temporary_injury_pressure: false,
    ...over,
  });
  const rows = buildTeamAnalysisRows({
    strengths: ['RB'],
    position_groups: [group('TE'), group('WR', { classification: 'short_term_need' }), group('QB', { upgrade_opportunity: true }), group('RB')],
  });
  assert.deepEqual(rows.map((r) => r.position), ['QB', 'RB', 'WR', 'TE']);
  assert.equal(rows[0].status, 'Upgrade opportunity');
  assert.equal(rows[1].status, 'Strength');
  assert.equal(rows[2].status, 'Thin');
  assert.equal(rows[3].status, 'Covered');
});
