import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import {
  normalizeCollegeProspects,
  normalizeCommissionerIntegrity,
  normalizeLeagueRankings,
  normalizeLeagueRosters,
  normalizeLeagueTeamProfiles,
  normalizeMe,
  normalizeSharedCommunityTrades,
} from './apiDefaults.ts';

const bodies: unknown[] = [{}, null, undefined, 'oops', [], { trades: null, teams: 'x' }];

test('an empty or malformed body becomes safe defaults', () => {
  for (const body of bodies) {
    const c = normalizeCommissionerIntegrity(body);
    assert.deepEqual([c.teams, c.collusion, c.inactive, c.limits], [[], [], [], []]);
    const p = normalizeCollegeProspects(body);
    assert.deepEqual(p.prospects, []);
    assert.equal(p.catalog_available, false);
    assert.deepEqual(normalizeSharedCommunityTrades(body).trades, []);
    assert.deepEqual(normalizeLeagueRosters(body).rosters, []);
    assert.deepEqual(normalizeLeagueTeamProfiles(body).profiles, {});
    assert.deepEqual(normalizeLeagueRankings(body).players, []);
  }
});

test('me without a user is a Free account with a fail-closed profile', () => {
  const r = normalizeMe({});
  assert.equal(r.user.entitlement, 'free');
  assert.equal(r.user.profile_status, 'error');
  assert.deepEqual(r.premium_benefits, []);
});

test('real data passes through and bad rows are dropped', () => {
  const r = normalizeCollegeProspects({ ok: true, prospects: [{ id: 'p1', name: 'A' }, null] });
  assert.equal(r.prospects.length, 1);
  assert.deepEqual(r.prospects[0].aggregate, { avg_grade: null, scout_count: 0, avg_round_projection: null });
});

test('twin stays byte-identical to web', () => {
  assert.equal(readFileSync('src/lib/apiDefaults.ts', 'utf8'), readFileSync('../web-next/src/lib/apiDefaults.ts', 'utf8'));
});

test('the module error boundary is wired into CompactModule and reports through the shared reporter', () => {
  const boundary = readFileSync('src/components/ModuleErrorBoundary.tsx', 'utf8');
  assert.ok(boundary.includes('getDerivedStateFromError') && boundary.includes('reportError('));
  assert.ok(boundary.includes('<ErrorState compact'));
  const compact = readFileSync('src/components/CompactModule.tsx', 'utf8');
  assert.ok(compact.includes('<ModuleErrorBoundary'));
});
