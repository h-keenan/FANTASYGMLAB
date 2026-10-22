import assert from 'node:assert/strict';
import { test } from 'node:test';

import { assetLabel, buildShareBody, gradeTone, isShareableGrade } from './sharedTrades.ts';

const verdict = { ui_verdict: 'ACCEPT', band: 'LEAN ACCEPT', rationale: 'x'.repeat(400) };

test('buildShareBody caps the reason and trims the display name', () => {
  const body = buildShareBody(
    verdict,
    [{ asset_type: 'player', name: 'A' }],
    [{ asset_type: 'pick', name: '2027 1st' }],
    '  Coach Z  ',
  );
  assert.equal(body.why.length, 280);
  assert.equal(body.display_name, 'Coach Z');
  assert.equal(body.grade, 'ACCEPT');
});

test('blank display name stays blank (server treats it as Anonymous)', () => {
  assert.equal(buildShareBody(verdict, [], [], '   ').display_name, '');
});

test('only analyzer grades are shareable', () => {
  assert.equal(isShareableGrade('FAIR'), true);
  assert.equal(isShareableGrade('IDEA'), false);
});

test('grade tones and labels', () => {
  assert.equal(gradeTone('ACCEPT'), 'success');
  assert.equal(gradeTone('DECLINE'), 'danger');
  assert.equal(gradeTone('COUNTER'), 'accent');
  assert.equal(gradeTone('FAIR'), 'neutral');
  assert.equal(assetLabel({ asset_type: 'player', name: 'A', position: 'WR' }), 'A · WR');
  assert.equal(assetLabel({ asset_type: 'pick', name: '2027 1st' }), '2027 1st');
});
