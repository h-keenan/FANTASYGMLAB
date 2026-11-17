// Run with: node --experimental-strip-types --test src/lib/avatarFallback.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { avatarChain, avatarMonogram, pickAvatarSource, teamLogoUrl } from './avatarFallback.ts';

test('real player: headshot, then monogram after a load error', () => {
  const input = { playerId: '4046', name: 'Patrick Mahomes', position: 'QB' };
  assert.deepEqual(avatarChain(input).map((s) => s.kind), ['headshot', 'monogram']);
  assert.equal(pickAvatarSource(input, []).kind, 'headshot');
  const after = pickAvatarSource(input, ['headshot:4046']);
  assert.equal(after.kind, 'monogram');
  assert.equal(after.kind === 'monogram' && after.label, 'PM');
});

test('team defense: logo (never a headshot), then monogram', () => {
  const input = { playerId: 'SF', name: '49ers D/ST', position: 'DEF', team: 'SF' };
  const first = pickAvatarSource(input, []);
  assert.equal(first.kind, 'teamLogo');
  assert.equal(first.kind === 'teamLogo' && first.url, 'https://sleepercdn.com/images/team_logos/nfl/sf.png');
  assert.equal(pickAvatarSource(input, [first.key]).kind, 'monogram');
});

test('made-up sim player (no id) gets the monogram straight away', () => {
  const s = pickAvatarSource({ playerId: null, name: 'Ranked Player 0', position: 'WR' }, []);
  assert.equal(s.kind, 'monogram');
  assert.equal(s.kind === 'monogram' && s.label, 'R0');
});

test('monogram is never empty', () => {
  assert.equal(avatarMonogram({}), '?');
  assert.equal(avatarMonogram({ team: 'buf' }), 'BUF');
  assert.equal(avatarMonogram({ name: 'Odell Beckham Jr.' }), 'OB');
  assert.equal(avatarMonogram({ name: 'Ignored', label: 'XY' }), 'XY');
  assert.equal(pickAvatarSource({}, ['anything']).kind, 'monogram');
});

test('rejects non-team codes for logos', () => {
  assert.equal(teamLogoUrl(''), null);
  assert.equal(teamLogoUrl('12'), null);
});
