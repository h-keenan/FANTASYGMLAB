// Run with: node --experimental-strip-types --test src/lib/playerTap.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { canOpenPlayer, isValidNonInteractiveReason, playerOpenLabel, PLAYER_TAP_MIN } from './playerTap.ts';

test('a player with an id can open, one without stays plain', () => {
  assert.equal(canOpenPlayer({ id: '7564', name: 'Ja' }), true);
  assert.equal(canOpenPlayer({ id: null, name: 'Rookie' }), false);
  assert.equal(canOpenPlayer({ id: '', name: 'Nobody' }), false);
  assert.equal(canOpenPlayer(null), false);
  assert.equal(playerOpenLabel('Kayshon Boutte'), 'Open Kayshon Boutte');
  assert.equal(PLAYER_TAP_MIN, 44);
});

test('a nonInteractive opt-out needs a real reason', () => {
  assert.equal(isValidNonInteractiveReason(''), false);
  assert.equal(isValidNonInteractiveReason('todo'), false);
  assert.equal(isValidNonInteractiveReason('the row button around it already opens the player'), true);
});

test('source scan: every player template is tappable or explicitly non-interactive (scripts/check_player_tap.mjs)', () => {
  const script = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../scripts/check_player_tap.mjs');
  const out = execFileSync('node', [script], { encoding: 'utf8' });
  assert.match(out, /passed/);
});
