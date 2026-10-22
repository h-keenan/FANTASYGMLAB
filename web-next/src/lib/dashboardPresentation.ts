import type { BriefingItem } from "@/lib/api";
import { formatGamePlanCategory } from "@/lib/gamePlanPresentation";

export type WatchTag = { label: string; color: string };

/**
 * The real usage-drop percentage a Value Trend item carries. The backend
 * (modules/dashboard_engine.build_value_trend_tile) writes it into the
 * item's note as "Usage down 37% (high confidence) ...". There is no
 * per-week series on the payload, so the dashboard shows this one number
 * and never draws a sparkline. Returns null when the item has no such
 * figure, so no indicator is rendered at all.
 */
export function usageTrendPct(item: BriefingItem): number | null {
  const text = `${item.reason ?? ""} ${item.supporting_context ?? ""}`;
  const match = /usage down (\d+(?:\.\d+)?)%/i.exec(text);
  if (!match) return null;
  const value = Number(match[1]);
  return Number.isFinite(value) ? value : null;
}

/** The TRENDING / INJURY / WAIVER tag for a non-top-priority briefing item. */
export function watchTag(item: BriefingItem): WatchTag {
  const category = (item.category || "").toLowerCase();
  if (category === "waiver_opportunity") return { label: "Waiver", color: "var(--color-success)" };
  if (usageTrendPct(item) !== null || /trend/i.test(item.headline)) {
    return { label: "Trending", color: "var(--color-danger)" };
  }
  if (item.route_player_injury_status || /injur/i.test(`${item.headline} ${item.reason}`)) {
    return { label: "Injury", color: "var(--color-warning)" };
  }
  return { label: formatGamePlanCategory(item.category) || "Watch", color: "var(--color-accent)" };
}
