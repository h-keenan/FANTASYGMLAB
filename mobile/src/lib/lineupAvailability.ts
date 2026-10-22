/**
 * Weekly lineup availability presentation, shared by My Team and Matchup.
 *
 * The server (services/mobile_api_service.py `_suggested_lineup_split`)
 * never starts a player on bye or ruled out in season: it benches him with
 * `start_ineligible_reason` and lists any starting slot nobody eligible
 * could fill in `open_slots`. Both fields are optional so an older API
 * build (or offseason response) renders exactly as before.
 */

export interface LineupAvailabilityFields {
  injury_label: string;
  on_bye?: boolean;
  start_ineligible_reason?: string | null;
}

/** The row pill: the server's injury label when there is one, else "Bye"
 * for a bye-week player, else ''. */
export function lineupStatusLabel(player: LineupAvailabilityFields): string {
  if (player.injury_label) return player.injury_label;
  if (player.on_bye || player.start_ineligible_reason === 'Bye') return 'Bye';
  return '';
}

/** True when the pill is only a bye (calmer "watch" tone, not injury red). */
export function isByeOnlyLabel(player: LineupAvailabilityFields): boolean {
  return !player.injury_label && lineupStatusLabel(player) === 'Bye';
}

/** Note for slots left open this week, or null when every slot is filled. */
export function openSlotsMessage(openSlots: string[] | null | undefined): string | null {
  if (!openSlots || openSlots.length === 0) return null;
  const label = openSlots.length === 1 ? 'slot' : 'slots';
  return `Open ${label} this week: ${openSlots.join(', ')}. Nobody on the roster can start there (bye or ruled out).`;
}
