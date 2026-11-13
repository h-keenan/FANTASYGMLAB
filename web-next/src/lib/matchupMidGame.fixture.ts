import type {
  MatchupRealStarter,
  MatchupResponse,
  MatchupSide,
  MatchupStarter,
  PlayerWeekProjection,
} from "./api";

/**
 * A realistic mid-game Sunday matchup payload (some starters live, some
 * final, some upcoming, a bye and an out player) used by the Matchup tests
 * and the screenshot harness. Not imported by app code.
 */

const KICKOFF_EARLY = "2026-11-08T18:00:00+00:00";
const KICKOFF_LATE = "2026-11-08T21:25:00+00:00";

const proj = (point: number | null, opponent: string | null, status: PlayerWeekProjection["status"] = "ok"): PlayerWeekProjection => ({
  status,
  point_estimate: point,
  low: point == null ? null : point - 4,
  high: point == null ? null : point + 5,
  confidence: "medium",
  opponent,
});

interface Spec {
  id: string;
  name: string;
  pos: string;
  team: string;
  slot: string;
  tier: string;
  ovr: number;
  projection: PlayerWeekProjection;
  game: "live" | "final" | "scheduled" | "bye";
  pts: number;
  projFinal?: number;
  progress?: number;
  opponent?: string;
  home?: boolean;
  injury?: string;
  teamScore?: number;
  oppScore?: number;
  kickoff?: string;
  stats?: Record<string, number>;
}

function toStarter(spec: Spec): MatchupRealStarter {
  const started = spec.game === "live" || spec.game === "final";
  return {
    player_id: spec.id,
    name: spec.name,
    position: spec.pos,
    team: spec.team,
    age: 25,
    status: "Active",
    injury_status: spec.injury ?? null,
    injury_label: spec.injury ?? "",
    tier: spec.tier,
    score: 1500,
    opportunity_label: null,
    overall_rating: spec.ovr,
    actual_points: started ? spec.pts : 0,
    projection: spec.projection,
    game_started: spec.game === "bye" ? null : started,
    game_final: spec.game === "final",
    game_status: spec.game === "live" ? "in_progress" : spec.game === "final" ? "final" : spec.game === "scheduled" ? "scheduled" : null,
    game_kickoff_at: spec.kickoff ?? (spec.game === "scheduled" ? KICKOFF_LATE : KICKOFF_EARLY),
    projected_final: spec.game === "live" ? (spec.projFinal ?? spec.pts) : null,
    game_progress: spec.game === "live" ? (spec.progress ?? 0.5) : spec.game === "final" ? 1 : null,
    game_opponent: spec.opponent ?? spec.projection.opponent,
    game_is_home: spec.home ?? null,
    game_team_score: spec.game === "final" ? (spec.teamScore ?? 24) : null,
    game_opponent_score: spec.game === "final" ? (spec.oppScore ?? 17) : null,
    slot: spec.slot,
    stats: spec.stats ?? null,
  };
}

/** `tick` advances the live games: more points, further along. */
export function midGameSpecs(tick = 0): { mine: Spec[]; opponent: Spec[] } {
  const t = tick;
  return {
    mine: [
      { id: "4984", name: "Josh Allen", pos: "QB", team: "BUF", slot: "QB", tier: "Elite", ovr: 94, projection: proj(22.4, "MIA"), game: "final", pts: 26.8, opponent: "MIA", home: true, teamScore: 31, oppScore: 20 },
      { id: "4866", name: "Saquon Barkley", pos: "RB", team: "PHI", slot: "RB", tier: "Elite", ovr: 91, projection: proj(17.1, "DAL"), game: "live", pts: 12.4 + t * 2.1, projFinal: 19.6 + t * 1.2, progress: Math.min(0.97, 0.52 + t * 0.06), opponent: "DAL", home: true, stats: { rush_att: 14 + t * 2, rush_yd: 71 + t * 9, rush_td: t >= 2 ? 1 : 0, rec: 2, rec_yd: 14 } },
      { id: "8110", name: "Bijan Robinson", pos: "RB", team: "ATL", slot: "RB", tier: "Elite", ovr: 90, projection: proj(16.3, "NO"), game: "scheduled", pts: 0, opponent: "NO", home: false, injury: "Questionable" },
      { id: "7564", name: "Ja'Marr Chase", pos: "WR", team: "CIN", slot: "WR", tier: "Elite", ovr: 95, projection: proj(18.9, "PIT"), game: "live", pts: 9.2 + t * 1.5, projFinal: 17.1 + t * 0.9, progress: Math.min(0.97, 0.52 + t * 0.06), opponent: "PIT", home: false, stats: { rec: 6 + t, rec_yd: 82 + t * 11, rec_td: 0 } },
      { id: "6786", name: "CeeDee Lamb", pos: "WR", team: "DAL", slot: "WR", tier: "Core Starter", ovr: 88, projection: proj(15.7, "PHI"), game: "live", pts: 5.1, projFinal: 11.8, progress: 0.52, opponent: "PHI", home: false, stats: { rec: 4, rec_yd: 41 } },
      { id: "5850", name: "Sam LaPorta", pos: "TE", team: "DET", slot: "TE", tier: "Core Starter", ovr: 80, projection: proj(null, null, "bye_week"), game: "bye", pts: 0 },
      { id: "6803", name: "Amon-Ra St. Brown", pos: "WR", team: "DET", slot: "FLEX", tier: "Elite", ovr: 92, projection: proj(16.2, null, "bye_week"), game: "bye", pts: 0 },
      { id: "7035", name: "Brandon Aubrey", pos: "K", team: "DAL", slot: "K", tier: "Depth", ovr: 70, projection: proj(8.4, "PHI"), game: "live", pts: 5 + (t >= 1 ? 3 : 0), projFinal: 8 + (t >= 1 ? 2 : 0), progress: 0.52, opponent: "PHI", home: false, stats: { fgm: 1 + (t >= 1 ? 1 : 0), xpm: 2 } },
      { id: "SF", name: "49ers D/ST", pos: "DEF", team: "SF", slot: "DEF", tier: "Depth", ovr: 60, projection: proj(7.0, "SEA"), game: "scheduled", pts: 0, opponent: "SEA", home: true },
    ],
    opponent: [
      { id: "4881", name: "Lamar Jackson", pos: "QB", team: "BAL", slot: "QB", tier: "Elite", ovr: 93, projection: proj(23.1, "CLE"), game: "final", pts: 19.3, opponent: "CLE", home: true, teamScore: 24, oppScore: 21 },
      { id: "3198", name: "Derrick Henry", pos: "RB", team: "BAL", slot: "RB", tier: "Core Starter", ovr: 86, projection: proj(14.8, "CLE"), game: "final", pts: 21.6, opponent: "CLE", home: true, teamScore: 24, oppScore: 21 },
      { id: "9221", name: "Chase Brown", pos: "RB", team: "CIN", slot: "RB", tier: "Core Starter", ovr: 83, projection: proj(13.2, "PIT"), game: "live", pts: 11.1 + t * 1.8, projFinal: 16.9 + t * 1.0, progress: Math.min(0.97, 0.52 + t * 0.06), opponent: "PIT", home: false, stats: { rush_att: 12 + t, rush_yd: 58 + t * 8, rec: 3, rec_yd: 22 } },
      { id: "8137", name: "Puka Nacua", pos: "WR", team: "LAR", slot: "WR", tier: "Elite", ovr: 94, projection: proj(17.9, "SEA"), game: "scheduled", pts: 0, opponent: "SEA", home: true },
      { id: "6797", name: "Jaylen Waddle", pos: "WR", team: "MIA", slot: "WR", tier: "Core Starter", ovr: 82, projection: proj(12.1, "BUF"), game: "final", pts: 7.4, opponent: "BUF", home: false, teamScore: 20, oppScore: 31 },
      { id: "1466", name: "Travis Kelce", pos: "TE", team: "KC", slot: "TE", tier: "Core Starter", ovr: 79, projection: proj(11.4, "DEN"), game: "scheduled", pts: 0, opponent: "DEN", home: true, injury: "Out" },
      { id: "4034", name: "Christian McCaffrey", pos: "RB", team: "SF", slot: "FLEX", tier: "Elite", ovr: 90, projection: proj(16.9, "SEA"), game: "scheduled", pts: 0, opponent: "SEA", home: true },
      { id: "4217", name: "Harrison Butker", pos: "K", team: "KC", slot: "K", tier: "Depth", ovr: 68, projection: proj(8.0, "DEN"), game: "scheduled", pts: 0, opponent: "DEN", home: true },
      { id: "BAL", name: "Ravens D/ST", pos: "DEF", team: "BAL", slot: "DEF", tier: "Depth", ovr: 65, projection: proj(8.2, "CLE"), game: "final", pts: 11, opponent: "CLE", home: true, teamScore: 24, oppScore: 21 },
    ],
  };
}

function side(name: string, rosterId: string, avatar: string | null, specs: Spec[], mine: boolean): MatchupSide {
  const real = specs.map(toStarter);
  const total = real.reduce((sum, p) => sum + (p.game_started ? (p.actual_points ?? 0) : 0), 0);
  return {
    roster_id: rosterId,
    team_name: name,
    owner_name: mine ? "coridian_" : "rival",
    avatar_url: avatar,
    wins: mine ? 6 : 5,
    losses: mine ? 2 : 3,
    ties: 0,
    starters: real as unknown as MatchupStarter[],
    season_value_total: mine ? 8200 : 7600,
    starters_basis: "suggested_optimal_lineup",
    real_starters: real,
    real_points: Math.round(total * 10) / 10,
    has_live_data: true,
    real_starters_basis: "sleeper_actual_lineup",
    real_empty_slots: [],
  };
}

export function midGameMatchup(tick = 0, asOfAgeSeconds = 12): MatchupResponse {
  const specs = midGameSpecs(tick);
  const mine = side("Dynasty Overlords", "1", null, specs.mine, true);
  const opponent = side("Rival Squad", "2", null, specs.opponent, false);
  const myTotal = mine.real_points ?? 0;
  const oppTotal = opponent.real_points ?? 0;
  return {
    ok: true,
    week: 10,
    my_team: mine,
    opponent,
    comparison: {
      my_season_value: 8200,
      opponent_season_value: 7600,
      margin: 600,
      edge: "you",
      headline: "Your lineup carries the stronger season-long value",
      basis: "season_value",
      basis_label: "Season-long value & opportunity signal, not a weekly points projection.",
    },
    real_comparison: {
      my_points: myTotal,
      opponent_points: oppTotal,
      margin: Math.round((myTotal - oppTotal) * 10) / 10,
      edge: myTotal > oppTotal ? "you" : myTotal < oppTotal ? "opponent" : "even",
      basis: "sleeper_actual_lineup",
      basis_label: "Your actual current-week lineup and live points, straight from Sleeper.",
    },
    win_probability: { available: true, probability: 0.58 + t(tick), my_projected_total: 121.4 + tick * 3, opponent_projected_total: 118.7 + tick * 2, coverage: { my: 1, opponent: 1 } },
    game_state: "live",
    position_edges: {
      actual: [
        { position: "WR", my_points: 40, opponent_points: 30, edge: 10, my_count: 3, opponent_count: 2, unmodeled: 0 },
        { position: "RB", my_points: 29, opponent_points: 41, edge: -12, my_count: 2, opponent_count: 3, unmodeled: 0 },
      ],
      suggested: [],
    },
    suggested_moves: [],
    basis: "season_value",
    basis_label: "Season-long value & opportunity signal, not a weekly points projection.",
    reason: "",
    as_of: "2026-11-08T19:42:00+00:00",
    as_of_age_seconds: asOfAgeSeconds,
    live: true,
    poll_after_seconds: 30,
  };
}

function t(tick: number): number {
  return Math.min(0.2, tick * 0.015);
}
