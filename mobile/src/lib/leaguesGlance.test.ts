// Run with: node --experimental-strip-types --test src/lib/leaguesGlance.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  glanceDestination,
  glanceFailedNote,
  glanceLayout,
  glanceNewsBadge,
  glanceRecordParts,
  glanceSectionState,
  glanceWaiverHeadline,
  ordinal,
} from './leaguesGlance.ts';

test('glanceLayout: exactly 2 cards render as a side-by-side grid', () => {
  assert.equal(glanceLayout(2), 'grid');
});

test('glanceLayout: 3 or more cards stack vertically', () => {
  assert.equal(glanceLayout(3), 'stack');
  assert.equal(glanceLayout(4), 'stack');
  assert.equal(glanceLayout(12), 'stack');
});

test('glanceLayout: a single surviving card stacks (no half-empty grid)', () => {
  assert.equal(glanceLayout(1), 'stack');
  assert.equal(glanceLayout(0), 'stack');
});

test('glanceSectionState: Free accounts with a saved league see the locked teaser', () => {
  assert.equal(glanceSectionState({ entitlement: 'free', profileStatus: 'ok', savedLeagueCount: 1 }), 'locked');
});

test('glanceSectionState: Premium with 2+ leagues is active', () => {
  assert.equal(glanceSectionState({ entitlement: 'premium', profileStatus: 'ok', savedLeagueCount: 2 }), 'active');
  assert.equal(glanceSectionState({ entitlement: 'premium', profileStatus: 'ok', savedLeagueCount: 5 }), 'active');
});

test('glanceSectionState: Premium with a single league has nothing to compare', () => {
  assert.equal(glanceSectionState({ entitlement: 'premium', profileStatus: 'ok', savedLeagueCount: 1 }), 'hidden');
});

test('glanceSectionState: never locks over an unverified plan or before leagues exist', () => {
  assert.equal(glanceSectionState({ entitlement: 'free', profileStatus: 'error', savedLeagueCount: 1 }), 'hidden');
  assert.equal(glanceSectionState({ entitlement: undefined, profileStatus: undefined, savedLeagueCount: 3 }), 'hidden');
  assert.equal(glanceSectionState({ entitlement: 'free', profileStatus: 'ok', savedLeagueCount: 0 }), 'hidden');
});

test('glanceRecordParts: record plus ordinal rank once standings are real', () => {
  assert.deepEqual(
    glanceRecordParts({
      wins: 6,
      losses: 2,
      ties: 0,
      record_label: '6-2',
      standing_rank: 1,
      team_count: 12,
      playoff_status: 'Playoff seed #1',
      standings_available: true,
    }),
    { record: '6-2', rank: '1st of 12' },
  );
  assert.deepEqual(
    glanceRecordParts({
      wins: 0,
      losses: 0,
      ties: 0,
      record_label: '0-0',
      standing_rank: null,
      team_count: 10,
      playoff_status: '',
      standings_available: false,
    }),
    { record: '0-0', rank: '' },
  );
  assert.deepEqual(glanceRecordParts(null), { record: '', rank: '' });
});

test('ordinal handles the teens', () => {
  assert.deepEqual([1, 2, 3, 4, 11, 12, 13, 21, 22, 23].map(ordinal), [
    '1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd', '23rd',
  ]);
});

test('glanceNewsBadge: injuries make the badge a risk tone', () => {
  assert.deepEqual(glanceNewsBadge({ news_count: 3, injury_count: 1 }), {
    count: 4,
    tone: 'risk',
    accessibilityLabel: '3 news items, 1 injured player. Opens league alerts.',
  });
  const quiet = glanceNewsBadge({ news_count: 2, injury_count: 0 });
  assert.equal(quiet.count, 2);
  assert.equal(quiet.tone, 'neutral');
  assert.equal(glanceNewsBadge(null).count, 0);
});

test('glanceWaiverHeadline: name with position and team', () => {
  assert.equal(
    glanceWaiverHeadline({ player_id: '1', name: 'Waiver Guy', position: 'WR', team: 'KC', reason: '' }),
    'Waiver Guy · WR · KC',
  );
  assert.equal(glanceWaiverHeadline({ player_id: '1', name: 'Waiver Guy', position: '', team: '', reason: '' }), 'Waiver Guy');
});

test('glanceDestination: each module jumps straight to its own feature screen', () => {
  assert.deepEqual(glanceDestination('record'), { screen: 'Dashboard' });
  assert.deepEqual(glanceDestination('waiver'), { screen: 'Waivers' });
  assert.deepEqual(glanceDestination('trade'), { screen: 'Trades', initialTab: 'block' });
  assert.deepEqual(glanceDestination('news'), { screen: 'Alerts' });
  assert.deepEqual(glanceDestination('need'), { screen: 'MyTeam' });
});

test('glanceFailedNote: names every league that failed', () => {
  assert.equal(glanceFailedNote([]), '');
  assert.equal(
    glanceFailedNote([{ league_id: 'a', league_name: 'Alpha', reason: 'unavailable' }]),
    "Couldn't load 1 league right now: Alpha.",
  );
  assert.equal(
    glanceFailedNote([
      { league_id: 'a', league_name: 'Alpha', reason: 'unavailable' },
      { league_id: 'b', league_name: 'Bravo', reason: 'not_a_member_of_league' },
    ]),
    "Couldn't load 2 leagues right now: Alpha, Bravo.",
  );
});
