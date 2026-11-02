import type { PlayerAvailability } from './api.ts';

/** Pure helpers for the quick view's availability + news blocks. Mirrors
 * web-next/src/lib/playerAvailabilityPresentation.ts (web/app parity). */

const INJURY_LABELS: Record<string, string> = {
  ir: 'Injured Reserve',
  'injured reserve': 'Injured Reserve',
  out: 'Out',
  pup: 'Physically Unable to Perform',
  sus: 'Suspended',
  suspended: 'Suspended',
  doubtful: 'Doubtful',
  questionable: 'Questionable',
  dnr: 'Did Not Report',
  cov: 'COVID-19 list',
};

/** "IR" -> "Injured Reserve" (never "Ir"). */
export function cleanInjuryLabel(status: string | null | undefined): string | null {
  const trimmed = (status ?? '').trim();
  if (!trimmed) return null;
  const mapped = INJURY_LABELS[trimmed.toLowerCase()];
  if (mapped) return mapped;
  return trimmed.charAt(0).toUpperCase() + trimmed.slice(1).toLowerCase();
}

/** Body part, then the honest return note; only fields the server returned. */
export function availabilityDetailParts(availability: PlayerAvailability): string[] {
  return [availability.body_part, availability.return_note].filter((part): part is string => Boolean(part));
}

/** Healthy: "On bye this week" badge carries the flag, pill stays "Bye: Wk N".
 * Out/IR: the bye is secondary, so the pill itself says "(this week)". */
export function byePillText(byeWeek: number, onByeThisWeek: boolean, unavailable: boolean): string {
  return onByeThisWeek && unavailable ? `Bye: Wk ${byeWeek} (this week)` : `Bye: Wk ${byeWeek}`;
}

export function newsAgeLabel(publishedTs: number | null, nowMs: number = Date.now()): string {
  if (!publishedTs) return '';
  const seconds = nowMs / 1000 - publishedTs;
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}
