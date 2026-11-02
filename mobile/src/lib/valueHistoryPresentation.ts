/**
 * Player value history presentation (chart caption, buy-low / sell-high copy).
 * Pure; mirrored by mobile/src/lib/valueHistoryPresentation.ts. Every string
 * describes only what the stored daily snapshots actually contain.
 */

export interface HistoryLike {
  status: string;
  points: { date: string; rating: number }[];
  span_days: number;
  first_date?: string | null;
  changes?: { days: number; delta: number }[];
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** '2026-10-12' -> 'Oct 12' (no timezone shifts: parsed from the string). */
export function shortDate(iso: string | null | undefined): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? '');
  if (!match) return '';
  return `${MONTHS[Number(match[2]) - 1] ?? ''} ${Number(match[3])}`;
}

export function formatRatingDelta(delta: number): string {
  if (delta === 0) return '0';
  return delta > 0 ? `+${delta}` : `${delta}`;
}

/** What to show under the chart. `null` = render nothing (storage unavailable). */
export function ratingHistoryCaption(
  history: HistoryLike | null | undefined,
): { chart: boolean; text: string; changes: string[] } | null {
  if (!history || history.status === 'unavailable') return null;
  if (history.status !== 'ok' || history.points.length < 2) {
    const first = shortDate(history.first_date ?? history.points[0]?.date);
    return {
      chart: false,
      text: first
        ? `Value history started ${first}. The chart appears once a second daily snapshot is stored.`
        : 'Value history has not started yet. Snapshots are stored once a day.',
      changes: [],
    };
  }
  const days = history.points.length;
  const first = shortDate(history.points[0].date);
  const last = shortDate(history.points[days - 1].date);
  return {
    chart: true,
    text: `${days} daily snapshots, ${first} to ${last} (${history.span_days} day${history.span_days === 1 ? '' : 's'} of history).`,
    changes: (history.changes ?? []).map((c) => `${formatRatingDelta(c.delta)} over ${c.days} days`),
  };
}

export interface SignalLike {
  rating_change: number;
  production_percentile: number;
  value_percentile: number;
  signal: 'buy_low' | 'sell_high';
  position: string;
}

/** One line naming both halves of the disagreement. */
export function signalReason(item: SignalLike): string {
  const trend = `Value ${formatRatingDelta(item.rating_change)}`;
  const gap = `production ${item.production_percentile}th pct vs value ${item.value_percentile}th`;
  return `${trend}, ${gap} among ${item.position}s`;
}

/** Empty/pending copy for the list; the real span is always stated. */
export function signalsStatusMessage(data: {
  status: string;
  span_days?: number;
  min_span_days?: number;
}): string | null {
  if (data.status === 'unavailable') return null;
  if (data.status === 'history_building') {
    const span = data.span_days ?? 0;
    const need = data.min_span_days ?? 7;
    return `Value history is still building: ${span} day${span === 1 ? '' : 's'} stored so far, ${need} needed before trends are shown.`;
  }
  return null;
}
