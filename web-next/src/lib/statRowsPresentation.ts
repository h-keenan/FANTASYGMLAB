import type { QuickViewStatItem, UsageMetric, UsageProfile } from "@/lib/api";
import { explorerStatKey } from "@/lib/percentileExplorer";
import { formatUsageDelta, formatUsageValue } from "@/lib/usageProfilePresentation";

/** One scannable stat row: label, value, percentile bar, a caption naming the
 * comparison pool, and an optional trend line. Shared by the Usage card, the
 * season Stats cards and the headline tiles, on web; mobile mirrors it. */
export interface StatRowModel {
  key: string;
  label: string;
  value: string;
  percentile: number | null;
  /** "vs RBs · 2026": who the percentile compares against, and which season. */
  caption: string | null;
  /** Small muted trend line, e.g. "Last 4: 70% (+17 pts vs earlier)". */
  trend: string | null;
  trendDirection?: UsageMetric["direction"];
  explorerKey: string | null;
}

export const COLLAPSE_AFTER = 4;

export function poolCaption(position: string | null | undefined, season: number | string | null | undefined): string | null {
  const pos = (position ?? "").toUpperCase();
  const parts = [pos ? `vs ${pos}s` : null, season ? String(season) : null].filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}

/** Season stat tiles -> rows. "Games" is availability, not performance: it is
 * already in the section title, so it is not a row. */
export function statItemRows(
  items: QuickViewStatItem[],
  position: string | null | undefined,
  season: number | null | undefined,
): StatRowModel[] {
  return items
    .filter((item) => item.label !== "Games")
    .map((item) => ({
      key: item.label,
      label: item.label,
      value: item.value,
      percentile: item.percentile,
      caption: item.percentile != null ? poolCaption(position, season) : null,
      trend: null,
      explorerKey: item.percentile != null ? explorerStatKey(item.label) : null,
    }));
}

/** Metrics worth a row: the five pool metrics (they carry an explorer key). */
export function usageRows(profile: UsageProfile, position: string | null | undefined): StatRowModel[] {
  return profile.metrics
    .filter((metric) => metric.explorer_key)
    .map((metric) => {
      const hasTrend = metric.last4 != null && metric.delta_last4_vs_prior != null;
      const last8 = metric.last8 != null ? ` · Last 8: ${formatUsageValue(metric, metric.last8)}` : "";
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

/** Whether the unified Usage card replaces the legacy season "Usage" tiles. */
export function usageCardCoversLegacyTiles(profile: UsageProfile | null | undefined): boolean {
  return Boolean(profile && profile.status !== "not_covered" && profile.metrics.some((metric) => metric.explorer_key));
}

/** Up to three headline numbers for the top of the view: points per game, then
 * the two usage numbers that matter most for the position. */
export function headlineRows(
  stats: { position: string; seasons: Array<{ season: number | null; fantasy: QuickViewStatItem[] }> } | null,
  profile: UsageProfile | null | undefined,
): StatRowModel[] {
  const out: StatRowModel[] = [];
  const season = stats?.seasons[0];
  if (stats && season) {
    const ppg = statItemRows(season.fantasy, stats.position, season.season).find((row) => row.label === "PPR PPG");
    if (ppg) out.push(ppg);
  }
  if (profile && stats) {
    const rows = usageRows(profile, stats.position);
    const wanted = stats.position.toUpperCase() === "RB" ? ["opportunity_share", "snap_share"] : ["target_share", "snap_share"];
    for (const key of wanted) {
      const row = rows.find((candidate) => candidate.key === key);
      if (row) out.push(row);
    }
  }
  return out.slice(0, 3);
}
