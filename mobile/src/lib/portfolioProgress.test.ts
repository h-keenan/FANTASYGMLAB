// Run with: node --experimental-strip-types --test src/lib/portfolioProgress.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import type { PortfolioIndexResponse, PortfolioLeague, PortfolioLeagueResponse } from './api.ts';
import { composePortfolio } from './portfolioProgress.ts';

const INDEX: PortfolioIndexResponse = {
  ok: true,
  is_premium: true,
  lens: 'Dynasty',
  leagues: [],
  failed_leagues: [],
  upsell: null,
  saved_leagues: [
    { league_id: 'a', league_name: 'Alpha' },
    { league_id: 'b', league_name: 'Bravo' },
    { league_id: 'c', league_name: 'Charlie' },
  ],
};

function row(leagueId: string, leagueName: string): PortfolioLeague {
  return { league_id: leagueId, league_name: leagueName, team_name: 'Team', power_rank: 1 } as PortfolioLeague;
}

function ok(league: PortfolioLeague): PortfolioLeagueResponse {
  return { ok: true, is_premium: true, lens: 'Dynasty', league, failed_league: null, upsell: null };
}

test('composePortfolio: every saved league is a placeholder row before anything arrives', () => {
  const composed = composePortfolio(INDEX, {});
  assert.deepEqual(
    composed.rows.map((r) => [r.kind, r.league.league_id]),
    [
      ['pending', 'a'],
      ['pending', 'b'],
      ['pending', 'c'],
    ],
  );
  assert.equal(composed.pendingCount, 3);
  assert.equal(composed.settled, false);
});

test('composePortfolio: a later league landing first keeps its saved position', () => {
  const composed = composePortfolio(INDEX, {
    c: { status: 'success', data: ok(row('c', 'Charlie')) },
    a: { status: 'pending' },
  });
  assert.deepEqual(
    composed.rows.map((r) => [r.kind, r.league.league_id]),
    [
      ['pending', 'a'],
      ['pending', 'b'],
      ['league', 'c'],
    ],
  );
  assert.deepEqual(
    composed.leagues.map((league) => league.league_id),
    ['c'],
  );
});

test('composePortfolio: server-side failures and request errors become failed leagues', () => {
  const composed = composePortfolio(INDEX, {
    a: { status: 'success', data: ok(row('a', 'Alpha')) },
    b: {
      status: 'success',
      data: {
        ok: true,
        is_premium: true,
        lens: 'Dynasty',
        league: null,
        failed_league: { league_id: 'b', league_name: 'Bravo', reason: 'empty_roster' },
        upsell: null,
      },
    },
    c: { status: 'error' },
  });
  assert.equal(composed.settled, true);
  assert.deepEqual(
    composed.rows.map((r) => r.league.league_id),
    ['a'],
  );
  assert.deepEqual(composed.failedLeagues, [
    { league_id: 'b', league_name: 'Bravo', reason: 'empty_roster' },
    { league_id: 'c', league_name: 'Charlie', reason: 'unavailable' },
  ]);
});

test('composePortfolio: a Free index has nothing to load', () => {
  const composed = composePortfolio({ ...INDEX, is_premium: false, saved_leagues: [] }, {});
  assert.equal(composed.rows.length, 0);
  assert.equal(composed.settled, true);
});
