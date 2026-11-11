/**
 * Pure helpers behind the notification controls (quiet hours, how often,
 * daily digest, per-league mute). Kept free of React so web and the app
 * (mobile/src/lib/notificationControls.ts, same logic) share one tested
 * behavior. Server side: modules/notification_prefs.py.
 */

import type {
  NotificationCapPreset,
  NotificationLeagueMode,
  NotificationPrefs,
  NotificationPrefsPatch,
  PushCategory,
} from "@/lib/api";

/** Non-urgent categories the single "daily digest" switch batches into one
 * morning push. Time-critical categories (injury, lineup lock, trade
 * deadline) are never digested, and waiver reminders are tied to a deadline,
 * so they stay instant. Must stay a subset of the server's digestible set. */
export const DIGEST_CATEGORIES: PushCategory[] = ["top_priority", "watch", "recap", "weekly_roundup", "team_situation"];

export const LEAGUE_MODE_OPTIONS: Array<{ value: NotificationLeagueMode; label: string; description: string }> = [
  { value: "all", label: "All", description: "Every alert for this league" },
  { value: "critical", label: "Urgent only", description: "Injuries, lineup locks and the trade deadline" },
  { value: "mute", label: "Muted", description: "Nothing from this league" },
];

export function hourLabel(hour: number): string {
  const h = ((Math.trunc(hour) % 24) + 24) % 24;
  const suffix = h < 12 ? "AM" : "PM";
  const twelve = h % 12 === 0 ? 12 : h % 12;
  return `${twelve} ${suffix}`;
}

export const HOUR_OPTIONS: Array<{ value: number; label: string }> = Array.from({ length: 24 }, (_, hour) => ({
  value: hour,
  label: hourLabel(hour),
}));

/** The preset matching the effective cap, or null for a custom value. */
export function activeCapPreset(
  prefs: Pick<NotificationPrefs, "weekly_cap">,
  presets: NotificationCapPreset[],
  defaultCap: number,
): string | null {
  const effective = prefs.weekly_cap ?? defaultCap;
  return presets.find((preset) => preset.cap === effective)?.key ?? null;
}

export function digestEnabled(prefs: Pick<NotificationPrefs, "category_modes">): boolean {
  return DIGEST_CATEGORIES.every((category) => prefs.category_modes[category] === "digest");
}

export function digestPatch(on: boolean): NotificationPrefsPatch {
  return {
    category_modes: Object.fromEntries(DIGEST_CATEGORIES.map((category) => [category, on ? "digest" : "instant"])),
  };
}

export function leagueMode(prefs: Pick<NotificationPrefs, "league_overrides">, leagueId: string): NotificationLeagueMode {
  return prefs.league_overrides[leagueId] ?? "all";
}

/** "7 AM to 10 PM" style summary; wraps midnight naturally. */
export function quietSummary(prefs: Pick<NotificationPrefs, "quiet_hours_enabled" | "quiet_start" | "quiet_end">): string {
  if (!prefs.quiet_hours_enabled) return "Off";
  return `${hourLabel(prefs.quiet_start)} to ${hourLabel(prefs.quiet_end)}`;
}

/** The device/browser IANA timezone, sent with quiet-hours edits so the
 * window means the user's own local time. "" when unavailable. */
export function deviceTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  } catch {
    return "";
  }
}
