/**
 * Usage-trend tile presentation for the Player Detail header (owner's PQV
 * concept, 2026-10-21). Same rules as web-next's usageTrendTone /
 * usageConfidenceBars (lib/playerQuickViewPresentation.ts), so a player's
 * usage reads the same color on both platforms.
 */

/** Rising usage is positive (green). A decline is danger (red) when it is a
 * confirmed read: high confidence, or a drop of 20% or more, the same
 * "declining role reads red" rule as PR #1308. A smaller,
 * moderate-confidence decline is neutral, never green. */
export function usageTrendTone(trend: {
  direction: 'up' | 'down';
  trend_pct: number;
  confidence_label: string;
}): 'positive' | 'danger' | 'neutral' {
  if (trend.direction === 'up') return 'positive';
  const highConfidence = trend.confidence_label.trim().toLowerCase().startsWith('high');
  if (highConfidence || Math.abs(trend.trend_pct) >= 20) return 'danger';
  return 'neutral';
}

/** Lit bars (of 3) for the confidence glyph: the backend only narrates
 * "high" or "moderate" reads, so 3 or 2; anything else shows 1. */
export function usageConfidenceBars(confidenceLabel: string): 1 | 2 | 3 {
  const normalized = confidenceLabel.trim().toLowerCase();
  if (normalized.startsWith('high')) return 3;
  if (normalized.startsWith('moderate')) return 2;
  return 1;
}

/** "High confidence" from the backend's "high confidence". */
export function sentenceCase(text: string): string {
  const trimmed = text.trim();
  return trimmed ? trimmed.charAt(0).toUpperCase() + trimmed.slice(1) : '';
}
