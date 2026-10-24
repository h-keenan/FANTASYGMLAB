// Pure helper: which resolved player identities a /v1/news story carries.
// Mirrors web-next NewsContent's NewsIdentity: a two-player entry wins when
// the backend sent exactly two; otherwise a single matched_player; otherwise
// none. Never invents a match — a story with no backend-resolved player
// renders no identity at all.

export interface NewsPlayerIdentity {
  matched_player: string | null;
  matched_player_id: string | null;
  matched_player_position: string | null;
  matched_player_team: string | null;
}

export interface NewsIdentitySource {
  matched_player?: string | null;
  matched_player_id?: string | null;
  matched_player_position?: string | null;
  matched_player_team?: string | null;
  matched_players?: NewsPlayerIdentity[] | null;
}

export function newsPlayerIdentities(item: NewsIdentitySource): NewsPlayerIdentity[] {
  if (Array.isArray(item.matched_players) && item.matched_players.length === 2) {
    return item.matched_players.filter((entry) => Boolean(entry?.matched_player));
  }
  if (item.matched_player) {
    return [
      {
        matched_player: item.matched_player,
        matched_player_id: item.matched_player_id ?? null,
        matched_player_position: item.matched_player_position ?? null,
        matched_player_team: item.matched_player_team ?? null,
      },
    ];
  }
  return [];
}
