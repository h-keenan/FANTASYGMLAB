import { test } from 'node:test';
import assert from 'node:assert/strict';

import { badgeTone, bandForScore, TRADE_VALUE_BANDS, TRADE_VALUE_GOLDEN } from './tradeValueBands.generated.ts';
import { sideLabelsCoverEveryBand, valueDirectionLabel } from './tradeValue.ts';
import { fairnessBandTone } from './liveDraft.ts';

test('the TS ladder replays the Python golden scores', () => {
  for (const { score, id } of TRADE_VALUE_GOLDEN) assert.equal(bandForScore(score).id, id, String(score));
});

test('quick compare words use the shared ladder and cover every band', () => {
  assert.ok(sideLabelsCoverEveryBand());
  assert.equal(valueDirectionLabel(600), 'Side B wins on value');
  assert.equal(valueDirectionLabel(-100), 'Value is essentially even');
  assert.equal(valueDirectionLabel(-1300), 'Large value gap favoring Side A');
});

test('badge tones are the band tones everywhere (live draft included)', () => {
  for (const band of TRADE_VALUE_BANDS) {
    assert.equal(badgeTone(band.badge), band.color_token);
    assert.equal(fairnessBandTone(band.badge), band.color_token);
  }
  assert.equal(fairnessBandTone('Slight Overpay'), 'warning');
});
