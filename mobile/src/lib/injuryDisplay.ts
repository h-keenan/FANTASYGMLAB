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
