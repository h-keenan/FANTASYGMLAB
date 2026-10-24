// Pure helpers behind the shared Player Quick View sheet (context/
// PlayerQuickViewContext.tsx + components/PlayerQuickViewSheet.tsx). Mirrors
// web-next's PlayerQuickViewContext: one identity shape every player tap
// passes in, one rule for what the sheet may show with / without a league.
import type { RankedPlayer } from './api.ts';

/** League the tap happened in. Absent for league-less surfaces (News). */
export interface QuickViewLeague {
  leagueId: string;
  leagueName: string;
}

export interface QuickViewRequest {
  player: RankedPlayer;
  /** Null when the tap came from a surface with no league (News). */
  league: QuickViewLeague | null;
  /** Small provenance label, e.g. "Waivers". Cosmetic. */
  sourceLabel?: string;
}

export function buildQuickViewRequest(
  player: RankedPlayer,
  league?: { leagueId?: string | null; leagueName?: string | null } | null,
  sourceLabel?: string,
): QuickViewRequest | null {
  if (!player?.player_id) return null;
  const leagueId = league?.leagueId?.trim();
  return {
    player,
    league: leagueId ? { leagueId, leagueName: league?.leagueName?.trim() || 'League' } : null,
    sourceLabel,
  };
}

/** A player known only by backend-resolved identity (a News story, a signal
 * row): every other field is null, never guessed. */
export function stubPlayer(identity: {
  player_id: string;
  name?: string | null;
  position?: string | null;
  team?: string | null;
}): RankedPlayer {
  return {
    player_id: identity.player_id,
    name: identity.name || null,
    position: identity.position || null,
    team: identity.team || null,
    age: null,
    status: null,
    injury_status: null,
    tier: null,
    score: null,
    overall_rank: null,
    position_rank: null,
    rank_unavailable_reason: null,
    opportunity_label: null,
  };
}

/** Where the sheet's "Full profile" action goes. PlayerDetail requires a
 * league, so a league-less open falls back to the user's last-used league
 * (navigation only; the sheet itself never shows that league's data), and
 * is null (action hidden) when there is none. */
export function fullProfileTarget(
  request: QuickViewRequest,
  fallback: QuickViewLeague | null,
): { player: RankedPlayer; leagueId: string; leagueName: string } | null {
  const league = request.league ?? fallback;
  if (!league) return null;
  return { player: request.player, leagueId: league.leagueId, leagueName: league.leagueName };
}

/** League-scoped fields (opportunity label) are only meaningful from a row
 * that came with league context; tier/ranks ride on the row itself. */
export function leagueScopedIdentity(request: QuickViewRequest): {
  tier: string | null;
  overallRank: number | null;
  positionRank: number | null;
  opportunityLabel: string | null;
} {
  const p = request.player;
  return {
    tier: p.tier ?? null,
    overallRank: p.overall_rank ?? null,
    positionRank: p.position_rank ?? null,
    opportunityLabel: request.league ? p.opportunity_label ?? null : null,
  };
}
