import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  DIRECTION_CHECKIN_INITIAL,
  directionCheckinPrompt,
  directionCheckinReducer,
  type DirectionCheckinResponse,
} from './directionCheckin.ts';

const SHOW: DirectionCheckinResponse = {
  ok: true,
  show: true,
  moment_key: '2026:midseason',
  stance: 'rebuilding',
  stance_label: 'Rebuilding',
  headline: 'Midseason: still Rebuilding?',
  body: 'Does Rebuilding still describe your team?',
  options: [{ value: 'competing', label: 'Competing' }],
};

test('only a complete show answer builds a prompt', () => {
  assert.equal(directionCheckinPrompt(null), null);
  assert.equal(directionCheckinPrompt({ ok: true, show: false, reason: 'no_moment' }), null);
  assert.equal(directionCheckinPrompt({ ...SHOW, headline: undefined }), null);
  assert.equal(directionCheckinPrompt(SHOW)?.keepLabel, 'Still fits');
});

test('an answered or quiet card never reopens', () => {
  const ready = directionCheckinReducer(DIRECTION_CHECKIN_INITIAL, { type: 'loaded', response: SHOW });
  assert.equal(ready.phase, 'ready');
  const hidden = directionCheckinReducer(directionCheckinReducer(ready, { type: 'save' }), { type: 'answered', action: 'dismissed' });
  assert.deepEqual(hidden, { phase: 'hidden' });
  assert.equal(directionCheckinReducer(hidden, { type: 'loaded', response: SHOW }), hidden);
  const changed = directionCheckinReducer(directionCheckinReducer(ready, { type: 'save' }), { type: 'answered', action: 'changed', label: 'Competing' });
  assert.deepEqual(changed, { phase: 'changed', label: 'Competing' });
});
