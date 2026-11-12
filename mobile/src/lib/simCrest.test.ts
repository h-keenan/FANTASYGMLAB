// Run with: node --experimental-strip-types --test src/lib/simCrest.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { simCrestArt, simCrestLetter, simCrestSpec } from './simCrest.ts';
import { simChecklistProgress, simMarginLine, simRowEdge, simStandingsWindow, simStrengthNeedLine, simTrendText, simWinChanceLabel } from './simGame.ts';

test('a team name always gets the same crest, and different teams differ', () => {
  assert.deepEqual(simCrestSpec('Gridiron Ghosts'), simCrestSpec('  gridiron ghosts '));
  const names = ['Gridiron Ghosts', 'Night Owls', 'Blitz Brigade', 'The Hail Marys', 'Dynasty Dogs', 'Red Zone Rebels', 'Waiver Wolves', 'Sunday Scaries', 'Fourth And Long', 'Pick Six', 'Trade Bait', 'Bye Week Bandits'];
  assert.ok(new Set(names.map((n) => JSON.stringify(simCrestSpec(n)))).size >= 11);
});

test('the crest letter skips filler words and the art is a 64 box', () => {
  assert.equal(simCrestLetter('The Hail Marys'), 'H');
  assert.equal(simCrestLetter(''), '?');
  const art = simCrestArt(simCrestSpec('Night Owls'));
  assert.equal(art.viewBox, '0 0 64 64');
  assert.ok(art.outline.startsWith('M'));
});

test('home dashboard helpers', () => {
  assert.equal(simWinChanceLabel(0.624), '62%');
  assert.deepEqual(simTrendText(6.14), { text: '+6.1', arrow: '▲', tone: 'success' });
  assert.equal(simTrendText(-4).tone, 'danger');
  assert.equal(simRowEdge({ you: { projection: 20 } as never, opp: { projection: 10 } as never }), 'you');
  assert.deepEqual(simChecklistProgress([{ done: true }, { done: false }]), { done: 1, total: 2 });
  assert.equal(simStrengthNeedLine(['RB'], ['TE']), 'Strong at RB. Needs TE.');
  assert.equal(simMarginLine({ margin: -2, in_playoffs: false, playoff_spots: 6, games_left: 5 }), '2 wins behind the cut line, 5 games left.');
  const rows = Array.from({ length: 12 }, (_, i) => ({ rank: i + 1, team_id: String(i), name: `T${i}`, is_you: i === 9, wins: 0, losses: 0, ties: 0, pf: 0, pa: 0 }));
  assert.equal(simStandingsWindow(rows, 6).length, 6);
});
