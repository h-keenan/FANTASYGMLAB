import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

// TestFlight build 56 was archived from a fresh worktree with no gitignored
// mobile/.env: Expo inlined EXPO_PUBLIC_* as `undefined`, src/lib/env.ts threw
// at module load, and the app never got past the native splash. Every release
// lane must run the env guard before building.
const here = dirname(fileURLToPath(import.meta.url));
const fastfile = readFileSync(join(here, '../../fastlane/Fastfile'), 'utf8');

function laneBody(platform: 'ios' | 'android', lane: string): string {
  const start = fastfile.indexOf(`platform :${platform} do`);
  assert.ok(start >= 0, `platform ${platform} missing`);
  const laneStart = fastfile.indexOf(`lane :${lane} do`, start);
  assert.ok(laneStart >= 0, `lane ${platform}/${lane} missing`);
  const next = fastfile.indexOf('\n  lane :', laneStart + 1);
  return fastfile.slice(laneStart, next === -1 ? undefined : next);
}

test('every build lane checks release env before building', () => {
  for (const [platform, lane] of [
    ['ios', 'beta'],
    ['ios', 'build_only'],
    ['android', 'beta'],
  ] as const) {
    assert.match(laneBody(platform, lane), /ensure_release_env/, `${platform}/${lane}`);
  }
});

test('guard requires the vars env.ts throws on', () => {
  const env = readFileSync(join(here, 'env.ts'), 'utf8');
  const required = [...env.matchAll(/requireEnv\(\s*'(EXPO_PUBLIC_[A-Z_]+)'/g)].map((m) => m[1]);
  assert.ok(required.length >= 3);
  for (const name of required) {
    assert.ok(fastfile.includes(name), `${name} missing from REQUIRED_RELEASE_ENV`);
  }
});

test('guard warns when analytics is explicitly disabled in a release build', () => {
  assert.match(fastfile, /EXPO_PUBLIC_ANALYTICS_ENABLED/);
  assert.match(fastfile, /UI\.important\([^)]*NO product analytics/);
  assert.ok(!/REQUIRED_RELEASE_ENV = %w\[[^\]]*ANALYTICS/.test(fastfile), 'analytics flag must not be required');
});
