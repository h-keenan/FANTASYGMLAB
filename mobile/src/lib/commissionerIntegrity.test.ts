import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

import {
  VETO_BAND_TICKS,
  vetoDeltaTone,
  vetoMeterPercent,
  vetoStandingLine,
  buildVetoRequest,
  formatSigned,
  vetoBandTone,
  vetoHasResult,
  vetoPointsLine,
  vetoPostureLabel,
  vetoStatusMessage,
  vetoWorstPositionLine,
  bandTone,
  integrityReasonMessage,
  calendarLines,
  integritySummaryLine,
  restSummary,
  splitTeams,
  type CommissionerIntegrityResponse,
  type IntegrityTeam,
} from './commissionerIntegrity.ts';

function shared(path: string): string {
  const text = readFileSync(resolve(process.cwd(), path), 'utf8');
  const start = text.indexOf('// SHARED BEGIN');
  const end = text.indexOf('// SHARED END');
  assert.ok(start >= 0 && end > start, `${path} missing SHARED markers`);
  return text.slice(start, end);
}

function team(band: IntegrityTeam['band'], id = 1): IntegrityTeam {
  return {
    roster_id: id, team_name: `T${id}`, owner_name: 'o', band, band_label: band, score: 0.5, confidence: 'medium',
    interpretation: 'none', context: 'alive', weeks: { evaluated: 5, flagged: 0, longest_streak: 0, latest_streak: 0 },
    evidence: [], innocent_explanations: [], series: [],
  };
}

function resp(teams: IntegrityTeam[]): CommissionerIntegrityResponse {
  return { ok: true, reason: '', teams, collusion: [], inactive: [], weeks_evaluated: 5 };
}

test('web and app share one league-integrity presentation block', () => {
  assert.equal(
    shared('src/lib/commissionerIntegrity.ts'),
    shared('../web-next/src/lib/commissionerIntegrity.ts'),
  );
});

test('bands map to fixed semantic tones', () => {
  assert.equal(bandTone('fine'), 'success');
  assert.equal(bandTone('worth_a_look'), 'warning');
  assert.equal(bandTone('strong'), 'danger');
  assert.equal(bandTone('not_enough_data'), 'muted');
});

test('summary is calm and flagged teams come first', () => {
  const teams = [team('strong', 1), team('fine', 2), team('worth_a_look', 3)];
  assert.deepEqual(splitTeams(teams).flagged.map((t) => t.roster_id), [1, 3]);
  assert.match(integritySummaryLine(resp(teams)), /not conclusions/);
  assert.match(integritySummaryLine(resp([team('fine')])), /No team stands out/);
});

test('reasons have honest copy', () => {
  assert.match(integrityReasonMessage('not_enough_weeks'), /three completed/);
  assert.match(integrityReasonMessage('weird'), /not available/);
});

test('restSummary is one line for a clean league and counts the rest otherwise', () => {
  const teams = Array.from({ length: 12 }, (_, i) => team('fine', i + 1));
  assert.equal(restSummary(teams, 0), 'All 12 teams look fine this week');
  assert.equal(
    restSummary([team('strong', 1), team('fine', 2), team('not_enough_data', 3)], 1),
    '1 other team looks fine this week; 1 without enough weeks yet',
  );
});

test('calendarLines shows deadline phase and playoff start', () => {
  const base = { trade_deadline_week: 11, current_week: 8, trade_deadline_passed: false, weeks_to_deadline: 3, deadline_phase: 'open' as const, playoff_week_start: 15, regular_season_weeks: 14, in_season: true };
  assert.deepEqual(calendarLines(base), ['Week 8 now', 'Trade deadline: after week 11 (3 weeks left)', 'Playoffs start week 15']);
  assert.ok(calendarLines({ ...base, deadline_phase: 'passed', trade_deadline_passed: true })[1].includes('passed'));
  assert.deepEqual(calendarLines(null), []);
});

test('veto bands use the same fixed tones as the integrity view', () => {
  assert.equal(vetoBandTone('fair'), 'success');
  assert.equal(vetoBandTone('explainable'), 'muted');
  assert.equal(vetoBandTone('lopsided'), 'warning');
  assert.equal(vetoBandTone('outrage'), 'danger');
});

test('veto copy helpers label postures and format numbers', () => {
  assert.equal(vetoPostureLabel('rebuild'), 'Rebuild');
  assert.equal(vetoPostureLabel(''), '');
  assert.equal(formatSigned(1240), '+1,240');
  assert.equal(formatSigned(-310), '-310');
  assert.equal(formatSigned(-3.24, 1), '-3.2');
  assert.equal(vetoPointsLine({ points_per_week: -3.2 }), 'Lineup -3.2 pts/wk');
  assert.equal(vetoWorstPositionLine({ worst_position: { position: 'WR', per_week_delta: -2.5 } }), 'Biggest hit: WR (-2.5 pts/wk)');
  assert.equal(vetoWorstPositionLine({ worst_position: null }), '');
});

test('buildVetoRequest rejects empty or same-team trades', () => {
  const base = { rosterA: '1', rosterB: '2', aPlayers: ['p1'], bPlayers: [], aPicks: [], bPicks: ['pick9'] };
  assert.deepEqual(buildVetoRequest(base), {
    roster_a: 1, roster_b: 2, a_sends_player_ids: ['p1'], b_sends_player_ids: [],
    a_sends_pick_ids: [], b_sends_pick_ids: ['pick9'], lens: 'Dynasty',
  });
  assert.equal(buildVetoRequest({ ...base, rosterB: '1' }), null);
  assert.equal(buildVetoRequest({ ...base, aPlayers: [], bPicks: [] }), null);
});

test('non-ok veto statuses show the server headline or honest copy', () => {
  assert.equal(vetoHasResult({ ok: true, status: 'invalid' }), false);
  assert.equal(vetoStatusMessage({ ok: true, status: 'invalid', headline: 'Pick two different teams.' }), 'Pick two different teams.');
  assert.match(vetoStatusMessage({ ok: true, status: 'unsupported_platform' }), /Sleeper/);
});

test('veto result helpers: meter, delta tone, standing line', () => {
  assert.deepEqual(VETO_BAND_TICKS, [20, 45, 70]);
  assert.equal(vetoMeterPercent(150), 100);
  assert.equal(vetoMeterPercent(-3), 0);
  assert.equal(vetoDeltaTone(900), 'positive');
  assert.equal(vetoDeltaTone(-1), 'risk');
  assert.equal(vetoDeltaTone(0), 'neutral');
  assert.equal(vetoStandingLine({ record: '0-7', standing: '#12 of 12' }), '0-7 · #12 of 12');
  assert.equal(vetoStandingLine({}), '');
});
