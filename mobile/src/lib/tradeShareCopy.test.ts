import assert from 'node:assert/strict';
import { test } from 'node:test';

import { plainTradeWhy } from './tradeShareCopy.ts';

test('a two-team surplus sentence keeps each clause with its own team', () => {
  assert.equal(
    plainTradeWhy('You can move from TE surplus; Rival can move from RB surplus.', 'Rival'),
    'You have TE depth to spare. Rival has RB depth to spare.',
  );
});

test('a clause that is not a plain surplus statement is dropped, never merged', () => {
  assert.equal(plainTradeWhy('You can move from TE surplus; the room is covered.', 'Rival'), '');
});

test('room needs still rewrite to plain English', () => {
  assert.equal(
    plainTradeWhy('RB: short-term starter coverage; Rival - WR: long-term upside.', 'Rival'),
    'You need an RB starter. Rival wants long-term WR upside.',
  );
});
