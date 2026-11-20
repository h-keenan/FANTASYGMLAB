import assert from 'node:assert/strict';
import test from 'node:test';

import { purgeAsyncStore, type AsyncKeyValueStore } from './accountScope.ts';
import { loadCollegeInterest, saveCollegeInterest } from './collegeInterestStore.ts';
import { createUserStorage } from './userStorageCore.ts';

function memoryStore(initial: Record<string, string> = {}): AsyncKeyValueStore & { data: Map<string, string> } {
  const data = new Map(Object.entries(initial));
  return {
    data,
    async getAllKeys() {
      return [...data.keys()];
    },
    async getItem(k) {
      return data.get(k) ?? null;
    },
    async setItem(k, v) {
      data.set(k, v);
    },
    async removeItem(k) {
      data.delete(k);
    },
  };
}

test('current user keeps a pre-existing answer after the upgrade (migration)', async () => {
  const store = memoryStore({
    'fgl:college-football-prompt-answered': '1',
    'fgl:college-football-interest': 'yes',
  });
  const us = createUserStorage(store);
  await us.applyUser('A');
  assert.equal(await loadCollegeInterest(us), 'yes');
  assert.equal(store.data.has('fgl:college-football-interest'), false);
  assert.equal(store.data.get('u:A:fgl:college-football-interest'), 'yes');
});

test('a second account does not inherit the first account answer', async () => {
  const store = memoryStore();
  const us = createUserStorage(store);
  await us.applyUser('A');
  await saveCollegeInterest(us, true);
  await us.applyUser('B');
  assert.equal(await loadCollegeInterest(us), 'unanswered');
  await saveCollegeInterest(us, false);
  assert.equal(await loadCollegeInterest(us), 'no');
  await us.applyUser('A');
  assert.equal(await loadCollegeInterest(us), 'yes');
});

test('the answer survives the sign-out purge for the same user', async () => {
  const store = memoryStore();
  const us = createUserStorage(store);
  await us.applyUser('A');
  await saveCollegeInterest(us, true);
  await us.set('fgl:last-league', 'x');
  await purgeAsyncStore(store);
  assert.equal(store.data.has('u:A:fgl:last-league'), false);
  await us.applyUser('A');
  assert.equal(await loadCollegeInterest(us), 'yes');
});

test('dismiss without answering reads as no', async () => {
  const us = createUserStorage(memoryStore());
  await us.applyUser('A');
  await saveCollegeInterest(us, null);
  assert.equal(await loadCollegeInterest(us), 'no');
});

test('signed out: nothing is read', async () => {
  const us = createUserStorage(memoryStore());
  assert.equal(await loadCollegeInterest(us), 'unanswered');
});
