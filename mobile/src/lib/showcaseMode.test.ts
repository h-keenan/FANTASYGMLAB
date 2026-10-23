import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  isShowcaseModeAvailable,
  maskShowcaseFields,
  maskShowcaseText,
  setShowcaseModeEnabled,
  unmaskShowcaseFields,
} from './showcaseMode.ts';

const SAMPLE = {
  league_name: 'Revivalary Dynasty',
  teams: [
    { roster_id: 1, team_name: 'Gridiron Gang', owner_name: 'Zach Real', avatar_id: null, avatar_url: 'https://x/a.png' },
    { roster_id: 2, team_name: 'Pat Mahomies', owner_name: 'Pat Smith', avatar_url: null },
  ],
  players: [{ player_id: '1', name: 'Patrick Mahomes', position: 'QB', team: 'KC' }],
  note: 'Pat Mahomies offered a trade for Patrick Mahomes',
  email: 'a@b.com',
};

test('no-op while off', () => {
  setShowcaseModeEnabled(false);
  assert.equal(maskShowcaseFields(SAMPLE), SAMPLE);
});

test('masks identities, drops avatars, keeps players; deterministic and idempotent', () => {
  setShowcaseModeEnabled(true);
  const out = maskShowcaseFields(SAMPLE);
  assert.equal(out.league_name, 'Sample League');
  assert.equal(out.teams[0].team_name, 'Team A');
  assert.equal(out.teams[1].owner_name, 'Manager 2');
  assert.equal(out.teams[0].avatar_url, null);
  assert.equal(out.email, 'hidden@example.com');
  assert.deepEqual(out.players, SAMPLE.players);
  assert.equal(out.note, 'Team B offered a trade for Patrick Mahomes');
  assert.deepEqual(maskShowcaseFields(SAMPLE), out);
  assert.deepEqual(maskShowcaseFields(out), out);
  assert.equal(maskShowcaseText('team', 'Gridiron Gang'), 'Team A');
  assert.equal(unmaskShowcaseFields({ league_name: 'Sample League' }).league_name, 'Revivalary Dynasty');
  setShowcaseModeEnabled(false);
});

test('availability: allowlist or founder_ops claim only', () => {
  assert.equal(isShowcaseModeAvailable('nobody@x.com'), false);
  assert.equal(isShowcaseModeAvailable('nobody@x.com', { founder_ops: true }), true);
  assert.equal(isShowcaseModeAvailable('KeenanHF@outlook.com'), true);
});
