// Shared (web + mobile twin): pure helpers for the Fantasy Sim "who has who" views. The League tab's Teams and
// Players views and the trade partner list all read one GET /league/rosters payload, so these run on it client side.

import type { SimGamePlayer, SimLeagueRosterTeam, SimPos } from "./simGame";

export type SimTeamChipTone = "danger" | "success";

export interface SimTeamChip {
  key: string;
  label: string;
  pos: SimPos;
  tone: SimTeamChipTone;
}

/** "Needs QB" / "Deep RB" chips for a team card: what it lacks vs where it has spare depth to trade from. */
export function simTeamChips(team: Pick<SimLeagueRosterTeam, "needs" | "surplus">): SimTeamChip[] {
  return [
    ...team.needs.map((pos): SimTeamChip => ({ key: `need-${pos}`, label: `Needs ${pos}`, pos, tone: "danger" })),
    ...team.surplus.map((pos): SimTeamChip => ({ key: `deep-${pos}`, label: `Deep ${pos}`, pos, tone: "success" })),
  ];
}

/** "3-0 · #3 · 269.4 PF" (or just the power rank before any game is played). */
export function simTeamRecordLine(team: Pick<SimLeagueRosterTeam, "record" | "power_rank">): string {
  const r = team.record;
  if (!r) return `Power #${team.power_rank}`;
  const rec = `${r.wins}-${r.losses}${r.ties ? `-${r.ties}` : ""}`;
  return r.wins + r.losses + r.ties === 0 ? `${rec} · Power #${team.power_rank}` : `${rec} · #${r.rank} · ${r.pf.toFixed(1)} PF`;
}

/** 11 = A+ ... 0 = F, -1 = no grade. Local on purpose: this file runs under the app's node test runner, which cannot resolve extensionless value imports. */
function gradeRank(grade: string | null | undefined): number {
  const order = ["F", "D", "D+", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+"];
  return grade ? order.indexOf(grade) : -1;
}

export interface SimRosterEntry {
  player: SimGamePlayer;
  team: Pick<SimLeagueRosterTeam, "team_id" | "name" | "is_you">;
}

export type SimRosterPosFilter = "ALL" | SimPos;

/** Everyone on a roster, best grade first, filtered by position and a name / NFL team search. */
export function simRosterEntries(teams: readonly SimLeagueRosterTeam[], pos: SimRosterPosFilter, query: string, blockOnly = false): SimRosterEntry[] {
  const needle = query.trim().toLowerCase();
  const out: SimRosterEntry[] = [];
  for (const team of teams) {
    for (const player of team.players) {
      if (pos !== "ALL" && player.pos !== pos) continue;
      if (blockOnly && !player.block) continue;
      if (needle && !player.name.toLowerCase().includes(needle) && !(player.team ?? "").toLowerCase().includes(needle)) continue;
      out.push({ player, team: { team_id: team.team_id, name: team.name, is_you: team.is_you } });
    }
  }
  return out.sort((a, b) => gradeRank(b.player.grade) - gradeRank(a.player.grade) || (b.player.ros_mean ?? 0) - (a.player.ros_mean ?? 0) || a.player.name.localeCompare(b.player.name));
}

/** Positions present in the league's rosters, in the usual order, for the filter pills. */
export function simRosterPositions(teams: readonly SimLeagueRosterTeam[]): SimPos[] {
  const order: SimPos[] = ["QB", "RB", "WR", "TE", "K", "DEF"];
  const have = new Set(teams.flatMap((t) => t.players.map((p) => p.pos)));
  return order.filter((p) => have.has(p));
}

/** Teams best-first by power rank, your own team kept in place (not pinned). */
export function simTeamsByPower<T extends Pick<SimLeagueRosterTeam, "power_rank">>(teams: readonly T[]): T[] {
  return [...teams].sort((a, b) => a.power_rank - b.power_rank);
}

/** Bench players grouped by position (for the team sheet), starters excluded. */
export function simGroupBenchByPosition(bench: readonly SimGamePlayer[], order: readonly string[]): { pos: string; players: SimGamePlayer[] }[] {
  const groups: { pos: string; players: SimGamePlayer[] }[] = [];
  for (const pos of order) {
    const players = bench.filter((p) => p.pos === pos);
    if (players.length) groups.push({ pos, players });
  }
  const known = new Set(order);
  const rest = bench.filter((p) => !known.has(p.pos));
  if (rest.length) groups.push({ pos: "OTHER", players: rest });
  return groups;
}

/** Players on any trade block (yours and the AI teams' this week), the league's shelf. */
export function simBlockEntryCount(teams: readonly SimLeagueRosterTeam[]): number {
  return teams.reduce((n, t) => n + t.players.filter((p) => p.block).length, 0);
}

/** "Selling depth · looking for RB · needs RB, WR": what an AI team shopping a player says about itself. */
export function simBlockNote(team: Pick<SimLeagueRosterTeam, "needs"> & { block?: SimLeagueRosterTeam["block"] }, why: string | undefined): string {
  const parts: string[] = [];
  if (why) parts.push(why);
  if (team.block?.looking_for) parts.push(`looking for ${team.block.looking_for}`);
  if (team.needs.length > 0) parts.push(`needs ${team.needs.join(", ")}`);
  return parts.join(" · ");
}
