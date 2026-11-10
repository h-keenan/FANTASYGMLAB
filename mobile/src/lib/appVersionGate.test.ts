import test from 'node:test';
import assert from 'node:assert/strict';
import { compareVersions, decideGate, fetchGate } from './appVersionGate.ts';

test('compareVersions handles ragged and numeric (not lexical) ordering', () => {
  assert.ok(compareVersions('1.9.0', '1.10.0')! < 0);
  assert.equal(compareVersions('1.2', '1.2.0'), 0);
  assert.ok(compareVersions('2.0.0', '1.99.99')! > 0);
  assert.equal(compareVersions('abc', '1.0.0'), null);
});

test('decideGate: blocks only below the platform floor', () => {
  const cfg = { min_app_version: { ios: '1.2.0', android: '' }, store_urls: { ios: 'https://s', android: 'https://p' } };
  assert.deepEqual(decideGate(cfg, 'ios', '1.1.9'), { updateRequired: true, storeUrl: 'https://s' });
  assert.equal(decideGate(cfg, 'ios', '1.2.0').updateRequired, false);
  assert.equal(decideGate(cfg, 'android', '0.0.1').updateRequired, false);
  assert.equal(decideGate(cfg, 'web', '0.0.1').updateRequired, false);
  assert.equal(decideGate(null, 'ios', '0.0.1').updateRequired, false);
});

test('fetchGate fails open on network error, bad status, and garbage floor', async () => {
  const base = { apiBaseUrl: 'https://api.test/', platform: 'ios', currentVersion: '1.0.0' };
  assert.equal((await fetchGate({ ...base, fetchFn: async () => { throw new Error('offline'); } })).updateRequired, false);
  assert.equal((await fetchGate({ ...base, fetchFn: async () => ({ ok: false, json: async () => ({}) }) })).updateRequired, false);
  assert.equal((await fetchGate({ ...base, fetchFn: async () => ({ ok: true, json: async () => ({ min_app_version: { ios: 'zzz' } }) }) })).updateRequired, false);
  const blocked = await fetchGate({ ...base, fetchFn: async (u) => {
    assert.equal(u, 'https://api.test/v1/app-config');
    return { ok: true, json: async () => ({ min_app_version: { ios: '2.0.0' }, store_urls: { ios: 'https://s' } }) };
  } });
  assert.deepEqual(blocked, { updateRequired: true, storeUrl: 'https://s' });
});
