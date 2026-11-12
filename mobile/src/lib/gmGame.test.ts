// Run with: node --experimental-strip-types --test src/lib/gmGame.test.ts
// Fantasy Sim: the GM Game on mobile. The call classifier is pure and tested
// directly; the screens (React Native, not loadable under plain node) are
// checked by source for the contract the web agent's hand-off asks for.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { runSimGameCall } from './simGameCall.ts';
import { ROUTE_BY_PAGE } from './orbTabs.ts';
import { NAV_PAGES } from './navCatalog.ts';
import { paidPreview } from './paidPreviews.ts';
import { simHeadshotId, simPlayerInitials, simSlotRepeatsPosition } from './simGame.ts';

const here = dirname(fileURLToPath(import.meta.url));
const read = (...p: string[]) => readFileSync(join(here, '..', ...p), 'utf8');

function harness() {
  const seen = { gates: [] as string[], errors: [] as string[], conflicts: 0 };
  return {
    seen,
    handlers: {
      onGate: (gate: { kind: string }) => seen.gates.push(gate.kind),
      onError: (message: string) => seen.errors.push(message),
      onConflict: () => {
        seen.conflicts += 1;
      },
    },
  };
}

test('a ready body is returned untouched and reports nothing', async () => {
  const h = harness();
  const body = await runSimGameCall(async () => ({ ok: true }), h.handlers);
  assert.deepEqual(body, { ok: true });
  assert.deepEqual(h.seen, { gates: [], errors: [], conflicts: 0 });
});

test('premium_required is a 200 that did nothing: null result plus a premium gate', async () => {
  const h = harness();
  const body = await runSimGameCall(async () => ({ ok: false, reason: 'premium_required', is_premium: false }), h.handlers);
  assert.equal(body, null);
  assert.deepEqual(h.seen.gates, ['premium']);
});

test('a conflict body and a thrown 409 both reload (onConflict) and report the gate', async () => {
  const h = harness();
  assert.equal(await runSimGameCall(async () => ({ reason: 'conflict' }), h.handlers), null);
  assert.equal(
    await runSimGameCall(async () => {
      throw Object.assign(new Error('Request failed (409).'), { status: 409 });
    }, h.handlers),
    null,
  );
  assert.equal(h.seen.conflicts, 2);
  assert.deepEqual(h.seen.gates, ['conflict', 'conflict']);
  assert.deepEqual(h.seen.errors, []);
});

test('404 is flag-off, 503 is busy, anything else is a plain message', async () => {
  const h = harness();
  const throwing = (error: unknown) => () => Promise.reject(error);
  await runSimGameCall(throwing(Object.assign(new Error('x'), { status: 404 })), h.handlers);
  await runSimGameCall(throwing(Object.assign(new Error('x'), { status: 503 })), h.handlers);
  await runSimGameCall(throwing(new Error('Request failed (500).')), h.handlers);
  await runSimGameCall(throwing(new Error('Pick not allowed')), h.handlers);
  assert.deepEqual(h.seen.gates, ['unavailable', 'unavailable']);
  assert.deepEqual(h.seen.errors, ['Something went wrong. Try again.', 'Pick not allowed']);
});

test('gm-game is a registered nav page with a route, a screen and an orb icon', () => {
  const page = NAV_PAGES.find((p) => p.key === 'gm-game');
  assert.ok(page, 'gm-game in the nav catalog');
  assert.equal(page.leagueScoped, false);
  assert.equal(ROUTE_BY_PAGE['gm-game'], 'GmGame');
  const navigator = read('navigation', 'RootNavigator.tsx');
  assert.match(navigator, /AppStack\.Screen\s+name="GmGame"/);
  assert.match(navigator, /GmGame: undefined;/);
  const orb = read('components', 'GmOrb.tsx');
  assert.match(orb, /'gm-game': 'game-controller-outline'/);
  assert.match(orb, /navPage\('gm-game'\)/);
  // Season Outlook stays a GM Plan tab.
  assert.ok(!('fantasy-sim' in ROUTE_BY_PAGE));
});

test('the Fantasy Sim upsell copy is registered for the Pro lock card', () => {
  const preview = paidPreview('fantasy_sim');
  assert.ok(preview && preview.bullets.length >= 3);
  assert.match(read('screens', 'GmGameScreen.tsx'), /feature="fantasy_sim"/);
});

test('the API methods hit /v1/sim/games* and advance sends the week', () => {
  const api = read('lib', 'api.ts');
  for (const path of ['/v1/sim/games/options', '"/v1/sim/games"', '/draft/pick', '/draft/auto', '/draft/queue', '/lineup/auto', '/waivers', '/trades/preview', '/inbox/', '/advance', '/revert-week', '/league`', '/result`']) {
    assert.ok(api.includes(path), path);
  }
  assert.match(api, /advanceSimGame: \(gameId: string, week: number\)[\s\S]*?jsonBody: \{ week \}/);
});

test('the screens render from the shared gating helpers, not private copies', () => {
  const screen = read('screens', 'GmGameScreen.tsx');
  for (const name of ['simFlowReducer', 'simGameGate', 'simNewGameBlock', 'simGamePaywalled', 'simAdvanceBlockers', 'simRecapsFromAdvance', 'useSimGameRequest']) {
    assert.ok(screen.includes(name), name);
  }
  // Advance sends the current week; a paywalled preview swaps Advance for Go Pro.
  assert.match(screen, /api\.advanceSimGame\(game\.id, game\.week\)/);
  assert.match(screen, /paywalled \?[\s\S]*?label="Go Pro"/);
  assert.match(screen, /disabled=\{Boolean\(block\)\}/);
  // Playoff rounds played in the same call (also_played) become extra recaps.
  assert.match(screen, /simRecapsFromAdvance\(res\.recap, res\.also_played\)/);
});

test('sim player photo helpers: Sleeper id or initials fallback', () => {
  assert.equal(simHeadshotId({ id: '4046', headshot_id: '4046' }), '4046');
  assert.equal(simHeadshotId({ id: '4046' }), '4046');
  assert.equal(simHeadshotId({ id: 'p0001', headshot_id: null }), null);
  assert.equal(simHeadshotId({ id: 'DEF-NYG' }), null);
  assert.equal(simPlayerInitials({ name: 'Patrick Mahomes II', pos: 'QB', team: 'KC' }), 'PI');
  assert.equal(simPlayerInitials({ name: 'NYG D/ST', pos: 'DEF', team: 'NYG' }), 'NYG');
});

test('every mobile sim list that names a player uses the shared chip or line', () => {
  for (const file of ['SimGameRecap.tsx', 'SimGameTeam.tsx', 'SimGameDraft.tsx', 'SimGameLeague.tsx']) {
    assert.match(read('components', file), /SimPlayerChip|SimPlayerLine/, file);
  }
  const parts = read('components', 'SimGameParts.tsx');
  assert.match(parts, /simHeadshotId\(player\)/);
  assert.doesNotMatch(parts, /PlayerAvatar playerId=\{player\.id\}/);
});

test('lineup rows drop the position chip only when the slot repeats it', () => {
  assert.equal(simSlotRepeatsPosition('RB', 'RB'), true);
  assert.equal(simSlotRepeatsPosition('FLEX', 'RB'), false);
  for (const file of ['SimGameTeam.tsx', 'SimGameRecap.tsx']) {
    assert.match(read('components', file), /hidePosition=\{simSlotRepeatsPosition\(/, file);
  }
});
