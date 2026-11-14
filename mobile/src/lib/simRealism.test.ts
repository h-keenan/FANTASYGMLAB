import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { test } from 'node:test';

import {
  SIM_REALISM_NOT_RETROACTIVE,
  simRealismBanner,
  simRealismBannerKey,
  simRealismEligible,
  simRealismGroups,
  simRealismParts,
  simRealismToast,
} from './simRealism.ts';

const flag = (name: string, boundary: 'now' | 'week' | 'season') => ({ flag: name, value: 1, label: name, body: `${name} body`, boundary, when: '' });
const info = (over: Record<string, unknown> = {}): any =>
  ({ rules_version: 0, eligible: true, pending: [flag('hint_v', 'now'), flag('world_v', 'week'), flag('aging_v', 'season')], scheduled: [], in_force: {}, history: [], note: '', ...over });
const game = (rules: unknown, status = 'in_season') => ({ id: 'g1', rules, status }) as never;

function read(path: string): string {
  return readFileSync(resolve(process.cwd(), path), 'utf8');
}

test('the update is offered only while a rule is off', () => {
  assert.equal(simRealismEligible(game(info())), true);
  assert.equal(simRealismEligible(game(info({ eligible: false }))), false);
  assert.equal(simRealismEligible(game(null)), false);
  assert.equal(simRealismEligible(game(undefined)), false);
  assert.deepEqual(simRealismGroups(info().pending).map((g: { boundary: string }) => g.boundary), ['now', 'week', 'season']);
});

test('Home banner: eligible old saves only, never once dismissed or finished', () => {
  assert.equal(simRealismBanner(game(info()), false)?.count, 3);
  assert.match(simRealismBanner(game(info()), false)?.body ?? '', new RegExp(SIM_REALISM_NOT_RETROACTIVE));
  assert.equal(simRealismBanner(game(info()), true), null);
  assert.equal(simRealismBanner(game(info(), 'complete'), false), null);
  assert.equal(simRealismBanner(game(info({ eligible: false })), false), null);
  assert.notEqual(simRealismBannerKey('g1', info()), simRealismBannerKey('g1', info({ rules_version: 1 })));
});

test('copy: menu header and toast', () => {
  assert.equal(simRealismParts(info())[0].text, '3 newer rules available');
  assert.equal(simRealismParts(info({ eligible: false, pending: [] }))[0].text, 'Up to date');
  assert.equal(simRealismToast({ upgraded: true, flags: ['a'] }), `Rules updated: 1 new rule on. ${SIM_REALISM_NOT_RETROACTIVE}`);
});

test('web and app wire the same pieces: menu entry, Home banner, confirm sheet, endpoint', () => {
  const pairs: [string, string][] = [
    ['src/components/SimRealism.tsx', '../web-next/src/components/SimRealism.tsx'],
    ['src/components/SimGameHome.tsx', '../web-next/src/components/SimGameHome.tsx'],
  ];
  for (const [app, web] of pairs) {
    for (const text of [read(app), read(web)]) {
      assert.match(text, /SimRealism/);
    }
  }
  for (const text of [read('src/components/SimRealism.tsx'), read('../web-next/src/components/SimRealism.tsx')]) {
    assert.match(text, /export function SimRealismSheet/);
    assert.match(text, /export function SimRealismModule/);
    assert.match(text, /export function SimRealismBanner/);
    assert.match(text, /sim\.menu\.realism/);
    assert.match(text, /realismUpgradeSimGame/);
    assert.match(text, /simRealismToast/); // the success toast
    assert.match(text, /SIM_REALISM_NOT_RETROACTIVE/); // the honest limit is on the confirm sheet
  }
  assert.match(read('src/screens/GmGameScreen.tsx'), /<SimRealismModule ctx=\{ctx\} \/>/);
  assert.match(read('../web-next/src/components/SimGameContent.tsx'), /<SimRealismModule ctx=\{ctx\} \/>/);
  assert.match(read('src/components/SimGameHome.tsx'), /<SimRealismBanner ctx=\{ctx\} \/>/);
  for (const api of [read('src/lib/api.ts'), read('../web-next/src/lib/api.ts')]) {
    assert.match(api, /realismUpgradeSimGame[\s\S]{0,160}\/realism-upgrade/);
  }
});
