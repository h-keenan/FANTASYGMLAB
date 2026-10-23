// Run with: node --experimental-strip-types --test src/lib/portfolioLoader.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  enabledLeagueIds,
  PORTFOLIO_LEAGUE_CONCURRENCY,
  PORTFOLIO_ROW_MIN_HEIGHT,
  PORTFOLIO_SHELL_SKELETON_COUNT,
  PORTFOLIO_SPLASH_DELAY_MS,
} from './portfolioLoader.ts';

const ORDER = ['a', 'b', 'c', 'd', 'e', 'f'];

test('enabledLeagueIds: only the first N unfetched leagues, in saved order', () => {
  const enabled = enabledLeagueIds(ORDER, {});
  assert.deepEqual([...enabled], ['a', 'b', 'c']);
  assert.equal(enabled.size, PORTFOLIO_LEAGUE_CONCURRENCY);
});

test('enabledLeagueIds: a finished league frees its slot for the next one in order', () => {
  assert.deepEqual([...enabledLeagueIds(ORDER, { a: true })], ['b', 'c', 'd']);
  assert.deepEqual([...enabledLeagueIds(ORDER, { a: true, b: true, c: true })], ['d', 'e', 'f']);
});

test('enabledLeagueIds: a failed (finished) league never blocks the rest', () => {
  // "b" errored -> counted as finished, so c, d fill in behind a.
  assert.deepEqual([...enabledLeagueIds(ORDER, { b: true })], ['a', 'c', 'd']);
});

test('enabledLeagueIds: nothing left when every league finished, and respects a custom cap', () => {
  assert.equal(enabledLeagueIds(ORDER, Object.fromEntries(ORDER.map((id) => [id, true]))).size, 0);
  assert.deepEqual([...enabledLeagueIds(ORDER, {}, 1)], ['a']);
});

test('constants: cap is 2-3, splash only after ~300ms, rows reserve height', () => {
  assert.ok(PORTFOLIO_LEAGUE_CONCURRENCY >= 2 && PORTFOLIO_LEAGUE_CONCURRENCY <= 3);
  assert.equal(PORTFOLIO_SPLASH_DELAY_MS, 300);
  assert.ok(PORTFOLIO_ROW_MIN_HEIGHT > 0);
  assert.ok(PORTFOLIO_SHELL_SKELETON_COUNT >= 1);
});
