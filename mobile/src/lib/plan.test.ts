import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';

import { glanceSectionState } from './leaguesGlance.ts';
import { isProOrNull, planOf, showProMarkers } from './plan.ts';

// Entitlement matrix: what /v1/me can say -> what every mobile surface does.
const MATRIX = [
  { name: 'Pro', user: { entitlement: 'premium', profile_status: 'ok' }, plan: 'pro', pro: true, markers: false, glance2: 'active' },
  { name: 'Front Office', user: { entitlement: 'front_office', profile_status: 'ok' }, plan: 'pro', pro: true, markers: false, glance2: 'active' },
  { name: 'Free', user: { entitlement: 'free', profile_status: 'ok' }, plan: 'free', pro: false, markers: true, glance2: 'locked' },
  { name: 'Unreadable profile', user: { entitlement: 'free', profile_status: 'error' }, plan: 'unknown', pro: null, markers: false, glance2: 'hidden' },
  { name: 'Garbage entitlement', user: { entitlement: 'banana', profile_status: 'ok' }, plan: 'free', pro: false, markers: true, glance2: 'locked' },
] as const;

for (const row of MATRIX) {
  test(`plan matrix: ${row.name}`, () => {
    assert.equal(planOf(row.user), row.plan);
    assert.equal(isProOrNull(row.user), row.pro);
    assert.equal(showProMarkers(row.user, false), row.markers);
    assert.equal(
      glanceSectionState({ entitlement: row.user.entitlement, profileStatus: row.user.profile_status, savedLeagueCount: 2 }),
      row.glance2,
    );
  });
}

test('an App Store / Play subscriber never wears Free markers even before the webhook lands', () => {
  assert.equal(showProMarkers({ entitlement: 'free', profile_status: 'ok' }, true), false);
});

test('not signed in / not loaded is unknown, never Free', () => {
  assert.equal(planOf(null), 'unknown');
  assert.equal(planOf(undefined), 'unknown');
});

test('no surface keeps its own Pro check: entitlement is only compared inside plan.ts', () => {
  const root = new URL('..', import.meta.url).pathname;
  const offenders: string[] = [];
  const walk = (dir: string) => {
    for (const name of readdirSync(dir)) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) walk(path);
      else if (/\.(ts|tsx)$/.test(name) && !/\.test\./.test(name) && !/(plan|apiDefaults)\.ts$/.test(name)) {
        if (/entitlement\s*[!=]==?\s*['"](premium|pro|free)['"]/.test(readFileSync(path, 'utf8'))) offenders.push(path);
      }
    }
  };
  walk(root);
  assert.deepEqual(offenders, [], 'use planOf()/isProOrNull() from lib/plan.ts');
});
