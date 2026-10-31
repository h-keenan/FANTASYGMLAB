import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

import {
  bandTone,
  integrityReasonMessage,
  integritySummaryLine,
  showCommissionerEntry,
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
  return { ok: true, reason: '', is_commissioner: true, teams, collusion: [], inactive: [], weeks_evaluated: 5 };
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

test('commissioner entry needs server confirmation; reasons have honest copy', () => {
  assert.equal(showCommissionerEntry(undefined), false);
  assert.equal(showCommissionerEntry({ ok: true, is_commissioner: false, reason: '' }), false);
  assert.equal(showCommissionerEntry({ ok: true, is_commissioner: true, reason: '' }), true);
  assert.match(integrityReasonMessage('not_enough_weeks'), /three completed/);
  assert.match(integrityReasonMessage('weird'), /not available/);
});
