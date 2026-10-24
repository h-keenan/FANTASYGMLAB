/**
 * Pure push-tap routing decision, split out of pushNotifications.ts so it can
 * be unit-tested under plain node (that module imports react-native / expo).
 *
 * Payload shapes come from modules/push_triggers.py:
 *  - league pushes: {league_id, league_name, category, player_id?, player_name?}
 *  - trade follow-up: {type: 'trade_outcome_followup', category:
 *    'trade_followup', outcome_id, league_id}
 */

export interface PushNotificationData {
  type?: string;
  league_id?: string;
  league_name?: string;
  category?: string;
  outcome_id?: string;
  player_id?: string;
  player_name?: string;
}

export type PushTapTarget =
  | { screen: 'PlayerDetail'; leagueId: string; leagueName: string; playerId: string; playerName: string }
  | { screen: 'LeagueDetail'; leagueId: string; leagueName: string }
  | { screen: 'TradeHistory' }
  | null;

function str(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

export function resolvePushTapTarget(data: unknown): PushTapTarget {
  if (!data || typeof data !== 'object') return null;
  const payload = data as PushNotificationData;
  const leagueId = str(payload.league_id);
  const leagueName = str(payload.league_name);

  // Trade follow-up ("Did this trade happen?") lands on Trade History, where
  // the pending outcome prompt lives. league_id is not needed for that.
  if (str(payload.type) === 'trade_outcome_followup' || str(payload.category) === 'trade_followup') {
    return { screen: 'TradeHistory' };
  }

  if (!leagueId) return null;

  const playerId = str(payload.player_id);
  if (playerId) {
    return { screen: 'PlayerDetail', leagueId, leagueName, playerId, playerName: str(payload.player_name) };
  }
  return { screen: 'LeagueDetail', leagueId, leagueName };
}
