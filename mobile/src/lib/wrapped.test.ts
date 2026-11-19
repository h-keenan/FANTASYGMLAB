import assert from 'node:assert/strict';
import { test } from 'node:test';

import { normalizeWrappedDeck, wrappedGradeTone, wrappedShareModel, wrappedShareText, wrappedShortName, wrappedView } from './wrapped.ts';

const P = { id: '1', headshot_id: '1', name: 'Marcus Hale', pos: 'RB', team: 'MIA' };
const card = (id: string, data: Record<string, unknown> | null, extra = {}) => ({ id, eyebrow: 'E', title: 'T', sub: null, pro: false, locked: false, data, ...extra });

test('short names are J. Surname', () => {
  assert.equal(wrappedShortName('Jalen Pruitt'), 'J. Pruitt');
  assert.equal(wrappedShortName('Marvin Harrison Jr.'), 'M. Harrison Jr.');
});

test('a grade is never red', () => {
  for (const g of ['A', 'B-', 'C', 'D', 'F']) assert.ok(['good', 'warm', 'neutral'].includes(wrappedGradeTone(g)));
});

test('deck parsing drops junk and bust carries the why', () => {
  assert.equal(normalizeWrappedDeck({ cards: [] }), null);
  const deck = normalizeWrappedDeck({ cards: [{ id: 'bust', data: { player: P, projected: 168, actual: 115.6, over_proj: -52.4, why: 'Missed 5 games: hamstring' } }] });
  assert.equal(deck?.cards.length, 1);
  const v = wrappedView(card('bust', { player: P, projected: 168, actual: 115.6, over_proj: -52.4, why: 'Missed 5 games: hamstring' }));
  assert.equal(v.kind, 'hero');
  if (v.kind === 'hero') assert.equal(v.hero, '-52.4');
});

test('locked cards have a teaser and no data; share text names the team', () => {
  const v = wrappedView(card('trades', null, { locked: true, pro: true }));
  assert.equal(v.kind, 'locked');
  const text = wrappedShareText(wrappedShareModel(card('luck', { actual_wins: 9, expected_wins: 10.6, diff: -1.6, games: 14 }), { season_label: 'S1', team_name: 'Comets' }));
  assert.match(text, /Comets/);
});
