/**
 * "Your team right now": the Dashboard hero's pure logic, shared by web and the
 * app. The block between the SHARED markers is byte-identical to
 * mobile/src/lib/teamStatus.ts (a mobile test compares them): edit both
 * together. Pure TS, no imports, so node --test can run it.
 *
 * Every field comes from a response the Dashboard already loads (matchup,
 * team-rankings, my-team-needs, season-sim, dashboard snapshot). Nothing is
 * estimated here: a missing input hides its row, it never becomes a 0.
 */

// SHARED BEGIN
export interface TeamStatusMatchupInput {
  week: number | null;
  reason?: string;
  my_team: { roster_id: string; team_name: string; avatar_url: string | null } | null;
  opponent: { team_name: string; owner_name: string | null; avatar_url: string | null } | null;
  win_probability?: {
    available: boolean;
    probability?: number;
    my_projected_total?: number;
    opponent_projected_total?: number;
  } | null;
  real_comparison?: { my_points: number; opponent_points: number } | null;
  game_state?: "pregame" | "live" | "between_games" | "final" | null;
  best_ball?: boolean;
  open_slots?: string[];
  suggested_moves?: {
    slot: string;
    start: { name: string | null };
    over: { name: string | null } | null;
    over_reason: "bye_week" | "ruled_out" | "empty_slot" | null;
    gain: number | null;
    locked: boolean;
  }[] | null;
}

export interface TeamStatusMatchup {
  week: number | null;
  opponentName: string;
  opponentAvatar: string | null;
  myName: string;
  myAvatar: string | null;
  /** Whole percent, this team's win chance; null when the model has no honest number. */
  winPercent: number | null;
  myProjected: number | null;
  opponentProjected: number | null;
  /** Real Sleeper points once both lineups are live. */
  live: { mine: number; opponent: number } | null;
  stateLabel: "Live" | "Final" | null;
}

function round1(value: number): number {
  return Math.round(value * 10) / 10;
}

/** This week's matchup line, or null (offseason, no opponent, bye week) so the row is hidden. */
export function buildTeamStatusMatchup(matchup: TeamStatusMatchupInput | null | undefined): TeamStatusMatchup | null {
  if (!matchup || matchup.reason || !matchup.my_team || !matchup.opponent) return null;
  const wp = matchup.win_probability;
  const modeled = Boolean(wp && wp.available && typeof wp.probability === "number");
  const live = matchup.real_comparison
    ? { mine: round1(matchup.real_comparison.my_points), opponent: round1(matchup.real_comparison.opponent_points) }
    : null;
  return {
    week: matchup.week ?? null,
    opponentName: matchup.opponent.team_name,
    opponentAvatar: matchup.opponent.avatar_url ?? null,
    myName: matchup.my_team.team_name,
    myAvatar: matchup.my_team.avatar_url ?? null,
    winPercent: modeled ? Math.round((wp!.probability as number) * 100) : null,
    myProjected: modeled && typeof wp!.my_projected_total === "number" ? round1(wp!.my_projected_total) : null,
    opponentProjected: modeled && typeof wp!.opponent_projected_total === "number" ? round1(wp!.opponent_projected_total) : null,
    live,
    stateLabel: matchup.game_state === "live" ? "Live" : matchup.game_state === "final" ? "Final" : null,
  };
}

export interface TeamStatusLineup {
  tone: "positive" | "risk" | "neutral";
  headline: string;
  detail: string | null;
}

/**
 * Lineup health from the matchup's suggested moves (the same ones the Matchup
 * page lists) plus the snapshot's injured-starter count. Null when neither is
 * known (best ball, offseason, no lineup yet).
 */
export function buildTeamStatusLineup(
  matchup: TeamStatusMatchupInput | null | undefined,
  injuredStarters: number | null | undefined,
): TeamStatusLineup | null {
  const injured = injuredStarters && injuredStarters > 0 ? injuredStarters : 0;
  const hasMoves = Boolean(matchup && !matchup.reason && !matchup.best_ball && Array.isArray(matchup.suggested_moves));
  const moves = hasMoves ? (matchup!.suggested_moves ?? []).filter((move) => !move.locked) : [];
  const fixes = moves.filter((move) => move.over_reason !== null);
  const openSlots = hasMoves ? (matchup!.open_slots ?? []).length : 0;
  const best = [...moves].sort((a, b) => (b.gain ?? 0) - (a.gain ?? 0))[0];
  const swap = best && best.start.name
    ? best.over?.name
      ? `Best swap: start ${best.start.name} over ${best.over.name}${best.gain && best.gain > 0 ? ` (+${round1(best.gain)} pts)` : ""}`
      : `Best swap: start ${best.start.name}${best.gain && best.gain > 0 ? ` (+${round1(best.gain)} pts)` : ""}`
    : null;
  const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;
  if (fixes.length > 0 || openSlots > 0) {
    const parts = [
      fixes.length > 0 ? `${plural(fixes.length, "starter")} can't play (bye or out)` : null,
      openSlots > 0 ? `${plural(openSlots, "open slot")}` : null,
    ].filter(Boolean);
    return { tone: "risk", headline: parts.join(", "), detail: swap };
  }
  if (injured > 0) {
    return { tone: "risk", headline: `${plural(injured, "injured starter")} on your roster`, detail: swap };
  }
  if (hasMoves) {
    return moves.length > 0
      ? { tone: "neutral", headline: "Lineup is healthy", detail: swap }
      : { tone: "positive", headline: "Lineup is set: no swaps needed", detail: null };
  }
  if (injuredStarters === 0) return { tone: "positive", headline: "No injured starters", detail: null };
  return null;
}

export interface TeamStatusRankingInput {
  roster_id: string;
  wins: number | null;
  losses: number | null;
  standing_rank?: number | null;
  playoff_status?: string | null;
  power_rank: number | null;
}

export interface TeamStatusSimInput {
  reason?: string;
  my_team: {
    playoff_probability: number;
    median_final_wins: number;
    median_final_losses: number;
    clinched: boolean;
    eliminated: boolean;
  } | null;
}

/** Playoff odds and projected record from the season simulator; null when it has nothing real (offseason, no roster). */
export function buildTeamStatusOdds(sim: TeamStatusSimInput | null | undefined): {
  playoffOdds: string | null;
  projectedRecord: string | null;
  clinched: boolean;
  eliminated: boolean;
} | null {
  if (!sim || sim.reason || !sim.my_team) return null;
  const mine = sim.my_team;
  return {
    playoffOdds: mine.clinched ? "Clinched" : mine.eliminated ? "Out" : `${Math.round(mine.playoff_probability)}%`,
    projectedRecord: `${mine.median_final_wins}-${mine.median_final_losses}`,
    clinched: mine.clinched,
    eliminated: mine.eliminated,
  };
}

export interface TeamStatusStanding {
  record: string | null;
  /** "3rd of 12" style place in the standings; null before standings exist. */
  place: string | null;
  playoffStatus: string | null;
  powerRank: number | null;
  /** Rest-of-season simulation: whole percent, or "Clinched" / "Out". */
  playoffOdds: string | null;
  projectedRecord: string | null;
  tone: "positive" | "risk" | "neutral";
}

function ordinal(n: number): string {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
  return `${n}${["th", "st", "nd", "rd"][n % 10 <= 3 ? n % 10 : 0]}`;
}

export function buildTeamStatusStanding(input: {
  snapshot: { wins: number | null; losses: number | null; ties: number | null } | null | undefined;
  rankings: TeamStatusRankingInput[] | null | undefined;
  standingsAvailable: boolean | undefined;
  myRosterId: string | null | undefined;
  odds: { playoffOdds: string | null; projectedRecord: string | null; clinched: boolean; eliminated: boolean } | null | undefined;
}): TeamStatusStanding | null {
  const { snapshot, rankings, odds } = input;
  const played = snapshot && snapshot.wins != null && snapshot.losses != null && snapshot.wins + snapshot.losses + (snapshot.ties ?? 0) > 0;
  const record = played ? `${snapshot!.wins}-${snapshot!.losses}${snapshot!.ties ? `-${snapshot!.ties}` : ""}` : null;
  const mine = input.myRosterId ? (rankings ?? []).find((team) => team.roster_id === input.myRosterId) : undefined;
  const placeKnown = Boolean(input.standingsAvailable && mine && mine.standing_rank != null && rankings && rankings.length > 0);
  const place = placeKnown ? `${ordinal(mine!.standing_rank as number)} of ${rankings!.length}` : null;
  const playoffStatus = placeKnown && mine!.playoff_status ? mine!.playoff_status : null;
  const row: TeamStatusStanding = {
    record,
    place,
    playoffStatus,
    powerRank: mine && mine.power_rank != null ? mine.power_rank : null,
    playoffOdds: odds?.playoffOdds ?? null,
    projectedRecord: odds?.projectedRecord ?? null,
    tone: odds?.clinched ? "positive" : odds?.eliminated ? "risk" : "neutral",
  };
  if (!row.record && !row.place && !row.playoffOdds) return null;
  return row;
}

export interface TeamStatusNeedsInput {
  strengths: string[];
  weaknesses: string[];
  position_groups: {
    position: string;
    classification: string;
    upgrade_opportunity: boolean;
    temporary_injury_pressure: boolean;
  }[];
}

export interface TeamStatusPosition {
  position: string;
  label: "Strength" | "Solid" | "Needs help" | "Aging risk";
  tone: "positive" | "neutral" | "risk" | "warning";
  /** The one room to improve first. */
  weakest: boolean;
}

const POSITION_ORDER = ["QB", "RB", "WR", "TE"];

/**
 * QB/RB/WR/TE room status from the league-relative need model (the same data
 * My Team's Strength and Pressure cards read). Rooms the model does not return
 * are omitted; nothing is flagged weakest when no room is a real need.
 */
export function buildTeamStatusPositions(needs: TeamStatusNeedsInput | null | undefined): TeamStatusPosition[] {
  if (!needs || !Array.isArray(needs.position_groups)) return [];
  const rows: TeamStatusPosition[] = [];
  for (const position of POSITION_ORDER) {
    const group = needs.position_groups.find((item) => item.position === position);
    if (!group) continue;
    const need = needs.weaknesses.includes(position) || group.classification === "short_term_need";
    const label: TeamStatusPosition["label"] = need
      ? "Needs help"
      : group.classification === "future_risk"
        ? "Aging risk"
        : needs.strengths.includes(position)
          ? "Strength"
          : "Solid";
    rows.push({
      position,
      label,
      tone: label === "Needs help" ? "risk" : label === "Aging risk" ? "warning" : label === "Strength" ? "positive" : "neutral",
      weakest: false,
    });
  }
  const rank = (row: TeamStatusPosition) => {
    const group = needs.position_groups.find((item) => item.position === row.position);
    const fromWeaknesses = needs.weaknesses.indexOf(row.position);
    return (fromWeaknesses >= 0 ? fromWeaknesses : 50) - (group?.upgrade_opportunity ? 0.5 : 0);
  };
  const needy = rows.filter((row) => row.label === "Needs help").sort((a, b) => rank(a) - rank(b));
  if (needy.length > 0) needy[0].weakest = true;
  return rows;
}
/** Mean roster age across the league (one decimal), for "League avg" context; null under 3 teams with an age. */
export function leagueAverageAge(teams: { average_age: number | null }[] | null | undefined): string | null {
  const ages = (teams ?? []).map((team) => team.average_age).filter((age): age is number => typeof age === "number" && Number.isFinite(age));
  if (ages.length < 3) return null;
  return (ages.reduce((sum, age) => sum + age, 0) / ages.length).toFixed(1);
}
// SHARED END
