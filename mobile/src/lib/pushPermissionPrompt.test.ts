import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  PUSH_PROMPT_COOLDOWN_MS as CD,
  isPushPromptCoolingDown,
  parseDismissedAt,
  shouldShowPushPrePrompt,
} from './pushPermissionPrompt.ts';

const now = 1_800_000_000_000;
const base = { permission: 'undetermined' as const, leagueLoaded: true, dismissedAt: null, now };

describe('shouldShowPushPrePrompt', () => {
  it('shows once a league has loaded and permission is undetermined', () => {
    assert.equal(shouldShowPushPrePrompt(base), true);
  });
  it('never shows before a league has loaded', () => {
    assert.equal(shouldShowPushPrePrompt({ ...base, leagueLoaded: false }), false);
  });
  it('never shows when granted, denied or unsupported', () => {
    for (const permission of ['granted', 'denied', 'unsupported'] as const) {
      assert.equal(shouldShowPushPrePrompt({ ...base, permission }), false);
    }
  });
  it('does not show twice in one session', () => {
    assert.equal(shouldShowPushPrePrompt({ ...base, askedThisSession: true }), false);
  });
  it('respects the 14 day cooldown after Not now', () => {
    assert.equal(shouldShowPushPrePrompt({ ...base, dismissedAt: now - CD + 1000 }), false);
    assert.equal(shouldShowPushPrePrompt({ ...base, dismissedAt: now - CD }), true);
    assert.equal(shouldShowPushPrePrompt({ ...base, dismissedAt: now - 1000 }), false);
  });
});

describe('cooldown helpers', () => {
  it('is 14 days', () => assert.equal(CD, 14 * 86_400_000));
  it('null means not cooling down', () => assert.equal(isPushPromptCoolingDown(null, now), false));
  it('a far-future timestamp cannot suppress forever', () => {
    assert.equal(isPushPromptCoolingDown(now + CD * 5, now), false);
  });
  it('parses stored values defensively', () => {
    assert.equal(parseDismissedAt(null), null);
    assert.equal(parseDismissedAt(''), null);
    assert.equal(parseDismissedAt('abc'), null);
    assert.equal(parseDismissedAt('0'), null);
    assert.equal(parseDismissedAt(String(now)), now);
  });
});
