import type { QuickViewStatItem, UsageMetric, UsageProfile } from './api.ts';
import { explorerStatKey } from './percentileExplorer.ts';
import { formatUsageDelta, formatUsageValue } from './usageProfile.ts';

// Presentation model for the shared stat row (label, value, percentile bar,
// pool caption, trend line). Mirrors web-next/src/lib/statRowsPresentation.ts.

export interface StatRowModel {
  key: string;
  label: string;
  value: string;
  percentile: number | null;
  caption: string | null;
  trend: string | null;
  trendDirection?: UsageMetric['direction'];
  explorerKey: string | null;
}

export const COLLAPSE_AFTER = 4;

export function poolCaption(position: string | null | undefined, season: number | string | null | undefined): string | null {
  const pos = (position ?? '').toUpperCase();
  const parts = [pos ? `vs ${pos}s` : null, season ? String(season) : null].filter(Boolean);
  return parts.length ? parts.join(' · ') : null;
}

export function statItemRows(
  items: QuickViewStatItem[],
  position: string | null | undefined,
  season: number | null | undefined,
): StatRowModel[] {
  return items
    .filter((item) => item.label !== 'Games')
    .map((item) => ({
      key: item.label,
      label: item.label,
      value: item.value,
      percentile: item.percentile ?? null,
      caption: item.percentile != null ? poolCaption(position, season) : null,
      trend: null,
      explorerKey: item.percentile != null ? explorerStatKey(item.label) : null,
    }));
}

export function usageRows(profile: UsageProfile, position: string | null | undefined): StatRowModel[] {
  return profile.metrics
    .filter((metric) => metric.explorer_key)
    .map((metric) => {
      const hasTrend = metric.last4 != null && metric.delta_last4_vs_prior != null;
      const last8 = metric.last8 != null ? ` · Last 8: ${formatUsageValue(metric, metric.last8)}` : '';
      return {
        key: metric.key,
        label: metric.label,
        value: formatUsageValue(metric, metric.season),
        percentile: metric.percentile ?? null,
        caption: metric.percentile != null ? poolCaption(position, profile.season) : null,
        trend: hasTrend
          ? `Last 4: ${formatUsageValue(metric, metric.last4)} (${formatUsageDelta(metric)} vs earlier)${last8}`
          : metric.last4 != null
            ? `Last 4: ${formatUsageValue(metric, metric.last4)}${last8}`
            : null,
        trendDirection: metric.direction,
        explorerKey: metric.percentile != null ? (metric.explorer_key ?? null) : null,
      };
    });
}

export function usageCardCoversLegacyTiles(profile: UsageProfile | null | undefined): boolean {
  return Boolean(profile && profile.status !== 'not_covered' && profile.metrics.some((metric) => metric.explorer_key));
}

export function headlineRows(
  stats: { position: string; seasons: Array<{ season: number | null; fantasy: QuickViewStatItem[] }> } | null,
  profile: UsageProfile | null | undefined,
): StatRowModel[] {
  const out: StatRowModel[] = [];
  const season = stats?.seasons[0];
  if (stats && season) {
    const ppg = statItemRows(season.fantasy, stats.position, season.season).find((row) => row.label === 'PPR PPG');
    if (ppg) out.push(ppg);
  }
  if (profile && stats) {
    const rows = usageRows(profile, stats.position);
    const wanted = stats.position.toUpperCase() === 'RB' ? ['opportunity_share', 'snap_share'] : ['target_share', 'snap_share'];
    for (const key of wanted) {
      const row = rows.find((candidate) => candidate.key === key);
      if (row) out.push(row);
    }
  }
  return out.slice(0, 3);
}
