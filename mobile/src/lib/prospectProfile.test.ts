// Run with: node --experimental-strip-types --test src/lib/prospectProfile.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  adpHeroTile,
  advancedTiles,
  gameStatLine,
  handOffPlayerId,
  heightLabel,
  lineTiles,
  normalizeProspectProfile,
  prospectMetaLine,
  prospectWeeklySeries,
  recruitingTiles,
  roundHeroTile,
} from './prospectProfile.ts';

test('size and header line come from what is on file only', () => {
  assert.equal(heightLabel(76), `6'4"`);
  assert.equal(heightLabel(null), null);
  assert.equal(prospectMetaLine(2027, { class_year: 3, height_in: 76, weight_lb: 220, hometown: null, school_logo_url: null }), `Class of 2027 · 6'4" · 220 lb`);
  assert.equal(prospectMetaLine(2027, null), 'Class of 2027');
});

test('stat tiles lead with the position main line', () => {
  const line = { passing: { yds: 3000, td: 25, int: 5, cmp: 200, att: 300 }, rushing: { yds: 200, td: 3, car: 50 } };
  assert.deepEqual(lineTiles(line, 'QB').slice(0, 3).map((t) => t.label), ['Pass yds', 'Pass TD', 'INT']);
  assert.equal(lineTiles(line, 'QB').find((t) => t.label === 'Comp %')?.value, '66.7%');
  assert.deepEqual(lineTiles({}, 'QB'), []);
});

test('weekly series skips games with no scoring and game lines read well', () => {
  assert.equal(gameStatLine({ passing: { yds: 312, td: 3 } }, 'QB'), '312 pass yds · 3 pass TD');
  const s = prospectWeeklySeries({ season: 2026, games: [{ week: 1, opponent: 'A', fantasy_points: 18 }, { week: 2, opponent: 'B', fantasy_points: null }] });
  assert.deepEqual(s?.weeks.map((w) => w.week), [1]);
  assert.equal(prospectWeeklySeries(null), null);
});

test('advanced, recruiting, ADP and round tiles never fill in what is missing', () => {
  const adv = advancedTiles({ season: 2026, ppa: { avg: { all: 0.42 } }, usage: { overall: 0.31 } }, 'QB');
  assert.deepEqual(adv.map((t) => `${t.label}=${t.value}`), ['PPA / play=+0.42', 'Usage=31%']);
  assert.deepEqual(advancedTiles(null, 'QB'), []);
  assert.deepEqual(recruitingTiles({ year: 2023, stars: 5, rating: 0.9998, national_rank: 1, high_school: null, city: null, state: null }).map((t) => t.value), ['5-star', '#1', '0.9998', '2023']);
  assert.equal(adpHeroTile(null).note, 'No ADP yet');
  assert.equal(roundHeroTile(1.6, 5).value, '2');
  assert.equal(roundHeroTile(null, 0).value, '—');
});

test('hand-off needs a Sleeper id; payload lists default', () => {
  assert.equal(handOffPlayerId({ sleeper_player_id: '12345' }), '12345');
  assert.equal(handOffPlayerId({ sleeper_player_id: null }), null);
  const body = normalizeProspectProfile({ ok: true });
  assert.deepEqual(body.seasons, []);
  assert.equal(body.weekly, null);
});
