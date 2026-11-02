import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  formatRatingDelta,
  ratingHistoryCaption,
  shortDate,
  signalReason,
  signalsStatusMessage,
} from './valueHistoryPresentation.ts';

test('shortDate and delta formatting', () => {
  assert.equal(shortDate('2026-10-12'), 'Oct 12');
  assert.equal(shortDate(null), '');
  assert.equal(formatRatingDelta(4), '+4');
  assert.equal(formatRatingDelta(-2), '-2');
});

test('caption states the real span and only supported changes', () => {
  const caption = ratingHistoryCaption({
    status: 'ok',
    points: [
      { date: '2026-10-01', rating: 60 },
      { date: '2026-10-09', rating: 66 },
    ],
    span_days: 8,
    changes: [{ days: 8, delta: 6 }],
  })!;
  assert.equal(caption.chart, true);
  assert.match(caption.text, /2 daily snapshots, Oct 1 to Oct 9 \(8 days of history\)/);
  assert.deepEqual(caption.changes, ['+6 over 8 days']);
});

test('short history draws no chart and unavailable hides', () => {
  const one = ratingHistoryCaption({
    status: 'insufficient_history',
    points: [{ date: '2026-10-01', rating: 60 }],
    span_days: 0,
    first_date: '2026-10-01',
  })!;
  assert.equal(one.chart, false);
  assert.match(one.text, /started Oct 1/);
  assert.equal(ratingHistoryCaption({ status: 'unavailable', points: [], span_days: 0 }), null);
  assert.equal(ratingHistoryCaption(null), null);
});

test('signal reason names both halves; building state states the span', () => {
  assert.equal(
    signalReason({ rating_change: -6, production_percentile: 80, value_percentile: 50, signal: 'buy_low', position: 'WR' }),
    'Value -6, production 80th pct vs value 50th among WRs',
  );
  assert.match(signalsStatusMessage({ status: 'history_building', span_days: 3, min_span_days: 7 })!, /3 days stored so far, 7 needed/);
  assert.equal(signalsStatusMessage({ status: 'ok' }), null);
});
