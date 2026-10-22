export type InjuryTone = 'success' | 'danger' | 'neutral';

/**
 * Coarse good/neutral/bad color read for a player's injury status cell.
 *
 * A null/absent `injuryStatus` means we have NO injury data for this
 * player — e.g. a push-notification deep link that only ever carries
 * player_id/name (see pushNotifications.ts's hand-built RankedPlayer), or
 * a player lookup that never resolved (quick-view `reason: 'not_found'`).
 * That must read as neutral/unknown, never the same green "success" tone
 * a player we've actually verified as healthy gets — conflating "no data"
 * with "confirmed healthy" is exactly the P0 bug this guards against
 * (a real out-for-season player showed a green "Healthy" pill because the
 * old code did `player.injury_status ?? 'Healthy'`).
 */
export function injuryTone(injuryStatus: string | null | undefined): InjuryTone {
  if (!injuryStatus) return 'neutral';
  const normalized = injuryStatus.toLowerCase();
  if (normalized.includes('healthy')) return 'success';
  if (normalized.includes('out') || normalized.includes('ir') || normalized.includes('doubtful')) return 'danger';
  return 'neutral';
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
