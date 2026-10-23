import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  hasIdpValues,
  idpMethodNote,
  idpRowsAsRankedPlayers,
  isIdpPositionFilter,
  playersPositionOptions,
  withIdpPositionOptions,
} from './idpPresentation.ts';

const BASE = ['ALL', 'QB', 'RB', 'WR', 'TE'];
const IDP = {
  ok: true as const,
  idp: true,
  below_replacement_ids: [],
  unscored_keys: ['bonus_def_int_td_50p'],
  players: [
    {
      player_id: 'd1',
      name: 'Edge Rusher',
      position: 'DE',
      family: 'DL' as const,
      team: 'DET',
      age: 26.1,
      injury_status: null,
      value: 2706,
      ppg: 15.54,
      projected_points: 240,
      points_over_replacement: 53,
      confidence: 'high' as const,
      idp_rank: 1,
    },
  ],
};

test('defense chips appear only in a league with IDP values', () => {
  assert.deepEqual(playersPositionOptions(BASE, IDP), [...BASE, 'DL', 'LB', 'DB']);
  assert.deepEqual(playersPositionOptions(BASE, null), BASE);
  assert.deepEqual(playersPositionOptions(BASE, { ok: true, idp: false, players: [] }), BASE);
  assert.deepEqual(playersPositionOptions(BASE, { ok: true, idp: true, players: [], reason: 'no_idp_scoring' }), BASE);
});

test('a non-IDP league yields no IDP rows', () => {
  assert.deepEqual(idpRowsAsRankedPlayers(null), []);
  assert.deepEqual(idpRowsAsRankedPlayers({ ok: true, idp: false, players: [] }), []);
  assert.equal(hasIdpValues(undefined), false);
});

test('rows adapt to RankedPlayer with value as score and the lineup family as position', () => {
  const [player] = idpRowsAsRankedPlayers(IDP);
  assert.equal(player.position, 'DL');
  assert.equal(player.score, 2706);
  assert.equal(player.overall_rank, 1);
  assert.equal(player.tier, null);
});

test('chips and the method note', () => {
  assert.equal(isIdpPositionFilter('LB'), true);
  assert.equal(isIdpPositionFilter('WR'), false);
  const note = idpMethodNote(IDP) ?? '';
  assert.ok(note.includes('not market prices'));
  assert.ok(note.includes('bonus_def_int_td_50p'));
  assert.equal(idpMethodNote(null), null);
});

test('withIdpPositionOptions adds DL/LB/DB only when defenders are present', () => {
  assert.deepEqual(withIdpPositionOptions(BASE, []), BASE);
  assert.deepEqual(withIdpPositionOptions(BASE, undefined), BASE);
  assert.deepEqual(withIdpPositionOptions(BASE, [{}]), [...BASE, 'DL', 'LB', 'DB']);
});

import { idpTradePoolPlayers, tradePositionOptions } from './idpPresentation.ts';

test('trade pool: below-replacement defenders carry a null score, non-IDP is empty', () => {
  const idp = {
    ...IDP,
    below_replacement_players: [
      { player_id: 'x1', name: 'Low Corner', position: 'CB', family: 'DB', team: 'NYJ', age: 23, injury_status: null, value: null },
    ],
  } as never;
  const pool = idpTradePoolPlayers(idp);
  assert.equal(pool[pool.length - 1].player_id, 'x1');
  assert.equal(pool[pool.length - 1].score, null);
  assert.deepEqual(idpTradePoolPlayers({ ok: true, idp: false, players: [] } as never), []);
  assert.deepEqual(tradePositionOptions(BASE, [{ position: 'QB' }]), BASE);
  assert.deepEqual(tradePositionOptions(BASE, pool), [...BASE, 'DL', 'LB', 'DB']);
});
