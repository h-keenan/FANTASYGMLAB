import { injuryTone as sharedInjuryTone, type InjuryToneName } from './injuryTone.generated.ts';

export type InjuryTone = InjuryToneName;

/**
 * Coarse good/warn/bad color read for a player's injury status cell: the one
 * shared map (injuryTone.generated.ts, from modules/injury_tone.py) that web
 * and the server badge also use. Doubtful/Out/IR are danger, Questionable is
 * warning, Healthy is success.
 *
 * A null/absent `injuryStatus` means we have NO injury data for this player
 * (a push deep link, an unresolved lookup). That reads neutral, never the
 * green "success" a verified-healthy player gets: conflating "no data" with
 * "confirmed healthy" was the P0 bug where an out-for-season player showed a
 * green "Healthy" pill.
 */
export function injuryTone(injuryStatus: string | null | undefined): InjuryTone {
  return sharedInjuryTone(injuryStatus);
}

const INJURY_ABBREVIATIONS: Record<string, string> = {
  questionable: 'Q',
  doubtful: 'D',
  out: 'O',
  ir: 'IR',
  'injured reserve': 'IR',
  suspended: 'SUS',
  sus: 'SUS',
  pup: 'PUP',
  probable: 'P',
  'day-to-day': 'DTD',
  'day to day': 'DTD',
  dtd: 'DTD',
  'non-football injury': 'NFI',
  nfi: 'NFI',
  covid: 'COV',
  'covid-19': 'COV',
  na: 'NA',
};

/**
 * Short code for an injury status, for the compact pill on a player row's
 * secondary line (PlayerIdentityRow). A full word like "Questionable" on
 * the name line took the name's width and cut it to "Ja..." (owner
 * screenshot, 2026-10-21). Same mapping as web-next's injuryAbbreviation
 * (lib/myTeamPresentation.ts). Unknown statuses fall back to their own text
 * when already short, or to the first three letters, so a status never
 * disappears.
 */
export function injuryAbbreviation(label: string | null | undefined): string {
  const trimmed = (label ?? '').trim();
  if (!trimmed) return '';
  const known = INJURY_ABBREVIATIONS[trimmed.toLowerCase()];
  if (known) return known;
  if (trimmed.length <= 4) return trimmed.toUpperCase();
  return trimmed.slice(0, 3).toUpperCase();
}
