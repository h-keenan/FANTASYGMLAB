import assert from 'node:assert/strict';
import test from 'node:test';

import { SAMPLE_ROSTER, SAMPLE_TRADE, sampleTradeVerdict } from './sampleLeague.ts';

test('sample trade verdict is deterministic', () => {
  const v = sampleTradeVerdict(SAMPLE_TRADE);
  assert.equal(v.giveTotal, 92);
  assert.equal(v.getTotal, 90);
  assert.equal(v.label, 'Fair');
});

test('sample dashboard maps to real Dashboard shapes with no player ids', async () => {
  const { sampleDashboardItems, sampleThisWeek, sampleTeamSnapshot, samplePulseTeams } = await import('./sampleDashboard.ts');
  const items = sampleDashboardItems();
  assert.equal(items.filter((i) => i.category === 'top_priority').length, 1);
  assert.ok(items.every((i) => i.route_player_id === '' && i.mentioned_players?.length === 0));
  assert.equal(sampleThisWeek().week, 6);
  assert.equal(sampleTeamSnapshot().power_rank, 3);
  assert.ok(samplePulseTeams().length > 2);
});

test('sample roster ids are unique', () => {
  const ids = SAMPLE_ROSTER.map((p) => p.id);
  assert.equal(new Set(ids).size, ids.length);
});
