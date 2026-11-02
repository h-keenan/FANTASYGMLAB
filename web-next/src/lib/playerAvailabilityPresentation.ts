import type { PlayerAvailability } from "./api";

/** Pure helpers for the quick view's availability + news blocks. Mirrored by
 * mobile/src/lib/playerAvailability.ts (web/app parity). */

const INJURY_LABELS: Record<string, string> = {
  ir: "Injured Reserve",
  "injured reserve": "Injured Reserve",
  out: "Out",
  pup: "Physically Unable to Perform",
  sus: "Suspended",
  suspended: "Suspended",
  doubtful: "Doubtful",
  questionable: "Questionable",
  dnr: "Did Not Report",
  cov: "COVID-19 list",
};

/** "IR" -> "Injured Reserve" (never "Ir"). Used for the pre-load chip, before
 * the server's availability block has arrived. */
export function cleanInjuryLabel(status: string | null | undefined): string | null {
  const trimmed = (status ?? "").trim();
  if (!trimmed) return null;
  const mapped = INJURY_LABELS[trimmed.toLowerCase()];
  if (mapped) return mapped;
  return trimmed.charAt(0).toUpperCase() + trimmed.slice(1).toLowerCase();
}

/** Detail line under the availability label: body part, then the honest
 * return note. Only fields the server actually returned. */
export function availabilityDetailParts(availability: PlayerAvailability): string[] {
  return [availability.body_part, availability.return_note].filter((part): part is string => Boolean(part));
}

/** Bye pill copy. For a healthy player the "On bye this week" badge carries
 * the current-week flag, so the pill stays "Bye: Wk 9". For a player who is
 * also out/IR the bye is secondary: no competing warning badge, and the pill
 * itself says "(this week)". */
export function byePillText(byeWeek: number, onByeThisWeek: boolean, unavailable: boolean): string {
  return onByeThisWeek && unavailable ? `Bye: Wk ${byeWeek} (this week)` : `Bye: Wk ${byeWeek}`;
}

/** Calendar-day age so "3d ago" matches what the News screen shows. */
export function newsAgeLabel(publishedTs: number | null, nowMs: number = Date.now()): string {
  if (!publishedTs) return "";
  const seconds = nowMs / 1000 - publishedTs;
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function newsPageHref(playerId: string, name: string): string {
  return `/news?player=${encodeURIComponent(playerId)}&name=${encodeURIComponent(name)}`;
}
