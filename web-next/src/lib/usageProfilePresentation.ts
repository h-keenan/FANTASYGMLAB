import type { UsageMetric, UsageProfile } from "@/lib/api";

/** Pure presentation helpers for model.usage_profile. The server decides every
 * threshold and flag (modules/usage_trends.py); these only format numbers. */

export function formatUsageValue(metric: UsageMetric, value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "–";
  return metric.unit === "pct" ? `${Math.round(value * 100)}%` : value.toFixed(1);
}

export function formatUsageDelta(metric: UsageMetric): string {
  const delta = metric.delta_last4_vs_prior;
  if (delta == null || !Number.isFinite(delta)) return "–";
  if (metric.unit === "pct") {
    const points = Math.round(delta * 100);
    return `${points > 0 ? "+" : ""}${points} pts`;
  }
  const rounded = Math.round(delta * 10) / 10;
  return `${rounded > 0 ? "+" : ""}${rounded.toFixed(1)}`;
}

/** The note shown under the table about what data this read used. */
export function usageDataNote(profile: UsageProfile): string | null {
  const advanced = profile.advanced;
  if (!advanced) return null;
  if (advanced.available) {
    return advanced.through_week ? `Target, air-yards and red-zone figures run through Week ${advanced.through_week}.` : null;
  }
  return "Target share, air yards and red-zone figures are not available for this player right now; snap share and touches come from Sleeper.";
}

/** Whether the block has anything honest to show. */
export function hasUsageContent(profile: UsageProfile | null | undefined): profile is UsageProfile {
  if (!profile) return false;
  if (profile.status === "not_covered") return false;
  return profile.metrics.length > 0 || profile.status === "unavailable";
}
