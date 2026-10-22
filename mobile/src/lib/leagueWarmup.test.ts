import assert from 'node:assert/strict';
import { test } from 'node:test';

import { followLeagueWarmup, type WarmupStatus } from './leagueWarmup.ts';

const status = (state: WarmupStatus['state'], roster = false, values = false, trades = false): WarmupStatus => ({
  ok: true,
  state,
  stages: { roster, values, trades },
});

test('cold league reports each real stage then finishes once', async () => {
  const queue = [status('running', true), status('running', true, true), status('done', true, true, true)];
  const seen: WarmupStatus[] = [];
  let done = 0;
  await new Promise<void>((resolve) => {
    followLeagueWarmup(
      async () => queue.shift()!,
      {
        onUpdate: (s) => seen.push(s),
        onDone: () => {
          done += 1;
          resolve();
        },
      },
      { intervalMs: 1 },
    );
  });
  assert.equal(done, 1);
  assert.deepEqual(seen.map((s) => s.stages.roster), [true, true, true]);
  assert.equal(seen[1].stages.trades, false);
});

test('warm league (none) hands off immediately', async () => {
  let done = 0;
  await new Promise<void>((resolve) => {
    followLeagueWarmup(async () => status('none'), { onUpdate: () => {}, onDone: () => { done += 1; resolve(); } });
  });
  assert.equal(done, 1);
});

test('a failing status request or an error state falls back to continuing', async () => {
  let done = 0;
  await new Promise<void>((resolve) => {
    followLeagueWarmup(async () => { throw new Error('down'); }, { onUpdate: () => {}, onDone: () => { done += 1; resolve(); } });
  });
  await new Promise<void>((resolve) => {
    followLeagueWarmup(async () => status('error', true), { onUpdate: () => {}, onDone: () => { done += 1; resolve(); } });
  });
  assert.equal(done, 2);
});

test('stops waiting after maxPolls and cancel prevents onDone', async () => {
  let done = 0;
  await new Promise<void>((resolve) => {
    followLeagueWarmup(
      async () => status('running'),
      { onUpdate: () => {}, onDone: () => { done += 1; resolve(); } },
      { intervalMs: 1, maxPolls: 3 },
    );
  });
  assert.equal(done, 1);

  let cancelledDone = 0;
  const cancel = followLeagueWarmup(
    async () => status('running'),
    { onUpdate: () => {}, onDone: () => { cancelledDone += 1; } },
    { intervalMs: 1 },
  );
  cancel();
  await new Promise((r) => setTimeout(r, 20));
  assert.equal(cancelledDone, 0);
});
