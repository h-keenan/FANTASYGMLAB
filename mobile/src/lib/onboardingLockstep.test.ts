import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

// Web and mobile onboarding are 3 steps (value, connect, level) with the same
// funnel ids/indexes. The mobile screen is React Native and cannot be imported
// under node:test, so compare the declared constants as text.
// npm test runs from mobile/, so these are cwd-relative string paths.
const mobile: string = readFileSync('src/screens/OnboardingScreen.tsx', { encoding: 'utf8' });
const web: string = readFileSync('../web-next/src/lib/onboardingFeatures.ts', { encoding: 'utf8' });

function listOf(src: string, name: string): string[] {
  const m = new RegExp(`${name}\\s*=\\s*\\[([^\\]]*)\\]`).exec(src);
  assert.ok(m, `${name} not found`);
  return [...m[1].matchAll(/['"]([a-z]+)['"]/g)].map((x) => x[1]);
}

test('onboarding funnel step ids match web', () => {
  const steps = listOf(mobile, 'STEP_KEYS');
  assert.deepEqual(steps, ['value', 'connect', 'level']);
  assert.deepEqual(listOf(web, 'ONBOARDING_STEP_KEYS'), steps);
});

test('onboarding value-step screenshots and headline match web', () => {
  assert.deepEqual(listOf(mobile, 'VALUE_SLIDE_KEYS'), listOf(web, 'ONBOARDING_VALUE_SLIDE_KEYS'));
  const headline = /VALUE_HEADLINE\s*=\s*'([^']+)'/.exec(mobile)?.[1];
  const webHeadline = /ONBOARDING_VALUE_HEADLINE\s*=\s*"([^"]+)"/.exec(web)?.[1];
  assert.ok(headline);
  assert.equal(headline, webHeadline);
});
