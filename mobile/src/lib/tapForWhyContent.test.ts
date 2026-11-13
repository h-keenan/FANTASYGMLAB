// Run with: node --experimental-strip-types --test src/lib/tapForWhyContent.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { WHY_REGISTRY, whyEntry, whyTriggerLabel } from './tapForWhyContent.ts';

test('every metric has a title and 1 to 3 plain sentences', () => {
  for (const entry of Object.values(WHY_REGISTRY)) {
    assert.ok(entry.title.length > 0, entry.id);
    assert.ok(entry.sentences.length >= 1 && entry.sentences.length <= 3, entry.id);
    for (const sentence of entry.sentences) assert.ok(sentence.trim().length > 0);
  }
});

test('entries are keyed by their own id and reuse the shared beginner copy', () => {
  for (const [key, entry] of Object.entries(WHY_REGISTRY)) assert.equal(entry.id, key);
  assert.match(whyEntry('ovr').sentences[0], /Overall \(1-99\)/);
});

test('trigger label is spoken text when given, else the entry title', () => {
  assert.equal(whyTriggerLabel('value', 'Value 82'), 'Why: Value 82');
  assert.equal(whyTriggerLabel('faab'), 'Why: FAAB bid');
});
