import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { test } from 'node:test';

import { canOpenTeam, teamDisplayName, teamLinkInteractive, teamOpenLabel, TEAM_TAP_MIN } from './teamTap.ts';

test('a team opens only with a league and a roster', () => {
  assert.equal(canOpenTeam({ leagueId: 'L1', rosterId: 4 }), true);
  assert.equal(canOpenTeam({ leagueId: 'L1', rosterId: '0' }), true);
  assert.equal(canOpenTeam({ leagueId: 'L1', rosterId: null }), false);
  assert.equal(canOpenTeam({ leagueId: '', rosterId: 4 }), false);
  assert.equal(canOpenTeam(null), false);
});

test("a team's own page stays plain", () => {
  assert.equal(teamLinkInteractive({ leagueId: 'L1', rosterId: 4 }, true), false);
  assert.equal(teamLinkInteractive({ leagueId: 'L1', rosterId: 4 }, false), true);
});

test('labels and minimum target', () => {
  assert.equal(teamOpenLabel('Just Win'), 'Open Just Win team sheet');
  assert.equal(teamOpenLabel(' '), 'Open team sheet');
  assert.equal(teamDisplayName(undefined), 'Team');
  assert.ok(TEAM_TAP_MIN >= 44);
});

test('the source guard passes (scripts/check_team_tap.mjs)', () => {
  const script = path.resolve(import.meta.dirname, '../../../scripts/check_team_tap.mjs');
  assert.match(execFileSync('node', [script], { encoding: 'utf8', stdio: 'pipe' }), /passed/);
});
