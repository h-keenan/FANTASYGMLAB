// Pure presentation helpers for the Fantasy Sim draft room. Byte-identical in
// web-next/src/lib and mobile/src/lib (scripts/check_lib_twins.mjs IDENTICAL).
import { compactParts, type CompactPart } from "./compactModule";
import { badgeFromTag, contextSuppressed, type BadgeInput, type BadgeKind } from "./playerBadges";
import { playerSurname } from "./playerNameDisplay";
import type { PlayerListStat } from "./playerListRow";
import { simGradeOf, simGradeText, type SimGradeInput } from "./simGrade";
import { simHeadshotId, simPlayerTags, simFmtPts, simFmtValue, simRosterNeeds, type SimDraftPick, type SimDraftState, type SimGamePlayer, type SimGameTone, type SimPlayerSort, type SimPos, type SimSlot } from "./simGame";

export interface SimDraftProgress {
  round: number;
  totalRounds: number;
  /** 1-based pick inside the round. */
  pickInRound: number;
  /** Picks made so far, 0..total. */
  made: number;
  total: number;
  /** 0..1 */
  fraction: number;
}

/** Round / pick progress for the hero bar. Teams is the league size. */
export function simDraftProgress(draft: Pick<SimDraftState, "pick_no" | "total_picks" | "status">, teams: number): SimDraftProgress {
  const total = Math.max(1, draft.total_picks);
  const size = Math.max(1, teams);
  const made = draft.status === "complete" ? total : Math.min(total, Math.max(0, draft.pick_no - 1));
  const current = Math.min(total, Math.max(1, draft.pick_no));
  return {
    round: Math.floor((current - 1) / size) + 1,
    totalRounds: Math.max(1, Math.ceil(total / size)),
    pickInRound: ((current - 1) % size) + 1,
    made,
    total,
    fraction: made / total,
  };
}

/** The newest `count` picks, newest first. */
export function simDraftRecentPicks(picks: SimDraftPick[] | undefined, count = 5): SimDraftPick[] {
  return [...(picks ?? [])].sort((a, b) => b.pick_no - a.pick_no).slice(0, count);
}

/** Two-letter emblem for a team ("Dynasty Dogs" -> "DD", "Rivals" -> "RI"). */
export function simDraftTeamEmblem(name: string | null | undefined): string {
  const words = (name ?? "").replace(/\(you\)/i, "").trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

/** Short countdown copy for the hero: "Your pick" / "Next pick in 4" / "Draft complete". */
export function simDraftNextPickLabel(draft: Pick<SimDraftState, "status" | "on_the_clock" | "picks_until_you" | "your_pick_numbers" | "pick_no">): { label: string; detail: string } {
  if (draft.status === "complete") return { label: "Done", detail: "Draft complete" };
  if (draft.on_the_clock?.is_you) return { label: "Now", detail: "You are on the clock" };
  const n = draft.picks_until_you;
  const next = draft.your_pick_numbers.find((p) => p >= draft.pick_no);
  if (n > 0) return { label: `${n}`, detail: `pick${n === 1 ? "" : "s"} until yours${next ? ` (#${next})` : ""}` };
  return { label: "-", detail: "No picks left for you" };
}

/** Best (first in list order) player at each position; the list is already ADP-sorted. */
export function simDraftBestByPosition(items: SimGamePlayer[], positions: SimPos[]): { pos: SimPos; player: SimGamePlayer | null }[] {
  return positions.map((pos) => ({ pos, player: items.find((p) => p.pos === pos) ?? null }));
}

export interface SimDraftNeed {
  pos: SimPos;
  have: number;
  starters: number;
  tone: SimGameTone;
}

/** Roster needs as colored pills: empty required spot is red, partly filled is amber, filled is green, no starter slot is muted. */
export function simDraftNeedPills(roster: Pick<SimGamePlayer, "pos">[], slots: SimSlot[]): SimDraftNeed[] {
  return simRosterNeeds(roster, slots).map((n) => ({
    ...n,
    tone: n.starters === 0 ? "muted" : n.have === 0 ? "danger" : n.have < n.starters ? "warning" : "success",
  }));
}

export interface SimDraftAdpDelta {
  /** adp minus the current pick: positive means he fell past his ADP. */
  delta: number;
  label: string;
  tone: SimGameTone;
}

/**
 * Board delta against the clock: ADP 10 still there at pick 16 is a +6 steal,
 * ADP 40 at pick 16 is a -24 reach. Within 3 picks is noise (null).
 */
export function simDraftAdpDelta(adp: number | null | undefined, pickNo: number): SimDraftAdpDelta | null {
  if (adp == null || Number.isNaN(adp)) return null;
  const delta = Math.round(pickNo - adp);
  if (Math.abs(pickNo - adp) < 3) return null;
  // Taking a player whose ADP is earlier than the pick is value (steal).
  return delta > 0 ? { delta, label: `+${delta}`, tone: "success" } : { delta, label: `${delta}`, tone: "danger" };
}

/**
 * Projection to show in a draft/board row. An injured or bye player projects
 * 0.0 for the current week (the engine scores him zero), which reads as "he is
 * bad"; show his per-game mean when healthy instead, flagged so the row can be
 * dimmed. Display only: engine scoring is untouched.
 */
export function simBoardProjection(player: { status?: string; projection: number; ros_mean?: number | null }): { value: number; discounted: boolean } {
  if (player.status && player.status !== "healthy" && player.ros_mean != null && player.ros_mean > 0) return { value: player.ros_mean, discounted: true };
  return { value: player.projection, discounted: false };
}

export interface SimDraftChip {
  key: "out";
  label: string;
  tone: SimGameTone;
}

/**
 * The only status chip a draft row shows: an injured/out player. Free agent is
 * implied, bye and rookie live in the muted meta line (simDraftMeta). The row
 * itself is never dimmed for an injury: an out player is still draftable.
 */
export function simDraftRowChips(player: Pick<SimGamePlayer, "status" | "out_weeks">): SimDraftChip[] {
  if (player.status !== "out") return [];
  return [{ key: "out", label: player.out_weeks > 0 ? `Out ${player.out_weeks}w` : "Out", tone: "danger" }];
}

/** How many game weeks (counting the current one) a bye counts as "soon" and gets the warning color. */
export const SIM_BYE_SOON_WEEKS = 3;

export interface SimDraftMetaPart {
  key: "team" | "age" | "bye";
  text: string;
  /** "warning" = a bye inside the next SIM_BYE_SOON_WEEKS weeks; An injury is the OUT chip, not meta text. */
  tone?: SimGameTone;
}

/**
 * The muted second line of a draft row: TEAM · Age 24.3 · Bye 7. The bye week
 * is ALWAYS shown (it used to appear only for byes in weeks 1-5, which read as
 * missing data); it turns into a warning color only when the bye is in the
 * next SIM_BYE_SOON_WEEKS game weeks (`week` is the current game week, 0 while
 * drafting, so weeks 1-3 then; null = unknown, never flags). Age shows a tenth when age_decimal is sent.
 */
export function simDraftMeta(player: Pick<SimGamePlayer, "team" | "age" | "bye_week" | "status" | "out_weeks"> & { age_decimal?: number | null }, week: number | null = 0): SimDraftMetaPart[] {
  const parts: SimDraftMetaPart[] = [];
  if (player.team) parts.push({ key: "team", text: player.team });
  const exact = player.age_decimal;
  const age = exact != null && !Number.isNaN(exact) ? exact.toFixed(1) : player.age != null && !Number.isNaN(player.age) ? `${Math.floor(player.age)}` : "";
  if (age) parts.push({ key: "age", text: `Age ${age}` });
  if (player.bye_week != null && player.bye_week > 0) {
    const from = Math.max(1, week ?? 1);
    const soon = week != null && player.bye_week >= from && player.bye_week < from + SIM_BYE_SOON_WEEKS;
    parts.push({ key: "bye", text: `Bye ${player.bye_week}`, tone: soon ? "warning" : undefined });
  }
  // Rookie is a glyph badge now (simRowBadges), not a word in this line.
  return parts;
}

/**
 * The squad / experience badges of a sim row: Rookie (the rookie flag, or a player 21 or younger), IR, Taxi. The injury
 * is the row's chip (simDraftRowChips, which becomes the Out badge), Free agent / On block / role come from the tags, so each
 * fact has one owner. Lists pass `contextSuppressed` over these so a rookie draft does not tag every row Rookie.
 */
export function simRowBadges(player: { rookie?: boolean; age?: number | null; squad?: string | null; status?: string | null }): BadgeInput[] {
  const out: BadgeInput[] = [];
  if (player.status === "bye") out.push({ kind: "bye" });
  if (player.squad === "ir") out.push({ kind: "ir" });
  if (player.squad === "taxi") out.push({ kind: "taxi" });
  if (player.rookie === true || (player.age != null && player.age <= 21.99)) out.push({ kind: "rookie" });
  return out;
}

/**
 * The labeled stats of a sim list row: PROJ, GRD (the player's overall as a LETTER GRADE, never a number: the sim shows no
 * numeric rating and no rank taken from it) and ADP. There is no "Edge" chip any more: it compared the model's value rank
 * with ADP, which would hand out the hidden ranking. Projection is the per-game mean for an injured player
 * (simBoardProjection), never a bare 0.0.
 */
export function simListStats(
  player: Pick<SimGamePlayer, "status" | "projection" | "ros_mean" | "adp"> & SimGradeInput,
  opts: { adp?: boolean } = {},
): PlayerListStat[] {
  const stats: PlayerListStat[] = [
    { key: "proj", label: "Proj", value: simFmtPts(simBoardProjection(player).value) },
  ];
  // The one overall is a letter grade. A pick or a thin position pool has none (null keeps the column's footprint).
  stats.push({ key: "ovr", label: "Grade", value: simGradeText(player), grade: simGradeOf(player) });
  if (opts.adp !== false && player.adp != null) stats.push({ key: "adp", label: "ADP", value: simFmtValue(player.adp) });
  return stats;
}

export interface SimDraftGridCell {
  round: number;
  teamId: string;
  pickNo: number | null;
  pick: SimDraftPick | null;
}

export interface SimDraftGrid {
  teams: { team_id: string; name: string; is_you: boolean }[];
  rows: SimDraftGridCell[][];
}

/**
 * Rounds x teams grid. Columns follow the round-1 order (or the team list when
 * the order is not sent); a snake draft still lines up because cells are keyed
 * by team and round.
 */
export function simDraftBoardGrid(draft: Pick<SimDraftState, "order" | "picks" | "teams" | "total_picks">, teamCount: number): SimDraftGrid {
  const order = draft.order ?? [];
  const teamsById = new Map((draft.teams ?? []).map((t) => [t.team_id, t]));
  const columnIds: string[] = [];
  for (const slot of order) {
    if (slot.round === 1 && !columnIds.includes(slot.team_id)) columnIds.push(slot.team_id);
  }
  for (const t of draft.teams ?? []) if (!columnIds.includes(t.team_id)) columnIds.push(t.team_id);
  const teams = columnIds.map((id) => ({ team_id: id, name: teamsById.get(id)?.name ?? "Team", is_you: Boolean(teamsById.get(id)?.is_you) }));
  const rounds = Math.max(1, Math.ceil(draft.total_picks / Math.max(1, teamCount)));
  const pickAt = new Map<string, SimDraftPick>();
  for (const pk of draft.picks ?? []) pickAt.set(`${pk.round}:${pk.team_id}`, pk);
  const pickNoAt = new Map<string, number>();
  for (const slot of order) pickNoAt.set(`${slot.round}:${slot.team_id}`, slot.pick_no);
  const rows: SimDraftGridCell[][] = [];
  for (let round = 1; round <= rounds; round += 1) {
    rows.push(
      teams.map((t) => {
        const key = `${round}:${t.team_id}`;
        const pick = pickAt.get(key) ?? null;
        return { round, teamId: t.team_id, pickNo: pick?.pick_no ?? pickNoAt.get(key) ?? null, pick };
      }),
    );
  }
  return { teams, rows };
}

/** "need RB/WR": the positions still short of their starter count, biggest hole first (at most three). Null when none. */
export function simDraftNeedLabel(needs: readonly SimDraftNeed[], max = 3): string | null {
  const short = needs
    .filter((n) => n.starters > 0 && n.have < n.starters)
    .sort((a, b) => b.starters - b.have - (a.starters - a.have))
    .slice(0, max)
    .map((n) => n.pos);
  return short.length ? `need ${short.join("/")}` : null;
}

/**
 * The collapsed draft-clock line (CompactModule `parts`): "R1 P2 · You pick now · need RB/WR · 1/192". The pick
 * action ("Draft Gibbs") is the module's trailing action, so it is usable without expanding. No pick clock exists in
 * the sim, so the status is who is up and how far away you are, never a countdown.
 */
export function simDraftSummaryParts(
  draft: Pick<SimDraftState, "status" | "pick_no" | "total_picks" | "on_the_clock" | "picks_until_you" | "your_pick_numbers">,
  teams: number,
  needs: readonly SimDraftNeed[],
  opts: { picking?: boolean } = {},
): CompactPart[] {
  if (draft.status === "complete") return [{ key: "done", text: "Draft complete", tone: "success", strong: true }];
  const progress = simDraftProgress(draft, teams);
  const onClock = Boolean(draft.on_the_clock?.is_you);
  const eta = simDraftNextPickLabel(draft);
  return compactParts([
    { key: "rp", text: `R${progress.round} P${progress.pickInRound}`, strong: true },
    opts.picking
      ? { key: "state", text: "Picking...", tone: "action", strong: true }
      : onClock
        ? { key: "state", text: "You pick now", tone: "action", strong: true }
        : { key: "state", text: `${eta.label} ${eta.detail}`.trim() },
    (() => {
      const need = simDraftNeedLabel(needs);
      return need ? { key: "need", text: need, tone: "warning" as const } : null;
    })(),
    { key: "n", text: `${progress.made}/${progress.total}`, tone: "muted" },
  ]);
}

export interface SimMiniCell {
  key: string;
  /** Position of the pick, or null while the slot is still open. */
  pos: string | null;
  you: boolean;
  /** The slot on the clock. */
  clock: boolean;
  pickNo: number | null;
}

/** The mini board: rounds x teams of tiny position-coloured cells (no names), for the always-visible overview. */
export function simDraftMiniBoard(draft: Pick<SimDraftState, "order" | "picks" | "teams" | "total_picks" | "pick_no" | "status">, teamCount: number): { you: boolean[]; rows: SimMiniCell[][] } {
  const grid = simDraftBoardGrid(draft, teamCount);
  const live = draft.status === "in_progress";
  return {
    you: grid.teams.map((t) => t.is_you),
    rows: grid.rows.map((row) =>
      row.map((cell, c) => ({
        key: `${cell.round}:${cell.teamId}`,
        pos: cell.pick?.player.pos ?? null,
        you: grid.teams[c].is_you,
        clock: live && !cell.pick && cell.pickNo === draft.pick_no,
        pickNo: cell.pickNo,
      })),
    ),
  };
}

/** One recent-pick chip's text: "#12 Lamb WR". */
export function simDraftPickChip(pick: Pick<SimDraftPick, "pick_no" | "player">): string {
  const parts = pick.player.name.trim().split(/\s+/);
  const last = parts.length > 1 ? parts[parts.length - 1] : pick.player.name;
  return `#${pick.pick_no} ${last} ${pick.player.pos}`;
}

/** The draft board's sorts. Grade is the shown rating (a coarse letter band, then projection); the model's internal value is never a sort or a label. */
export const SIM_DRAFT_SORTS: { label: string; value: SimPlayerSort }[] = [
  { label: "ADP", value: "adp" },
  { label: "Proj", value: "projection" },
  { label: "Grade", value: "overall" },
];

/** Next sort in the draft list (a one-tap cycle on phones). Unknown values restart at the first. */
export function simCycleSort(current: string): SimPlayerSort {
  const i = SIM_DRAFT_SORTS.findIndex((s) => s.value === current);
  return SIM_DRAFT_SORTS[(i + 1) % SIM_DRAFT_SORTS.length].value;
}

/** The rounds the mini board shows: the one on the clock and a little context either side (the full grid is one tap away). */
export function simDraftMiniWindow<T>(rows: readonly T[][], currentRound: number, size = 4): { rows: T[][]; from: number; to: number } {
  const n = rows.length;
  const span = Math.min(size, n);
  const start = Math.max(0, Math.min(n - span, currentRound - 2));
  return { rows: rows.slice(start, start + span) as T[][], from: start + 1, to: start + span };
}

/**
 * The badge kinds to leave off every row of a list because they are true of the whole list: a rookie draft board is all
 * Rookie, a free-agent board is all Free agent (coridian_: "a rookie draft should not even have a rookie tag because it's
 * obvious"). Health badges are never suppressed (contextSuppressed).
 */
export function simSuppressedBadges(players: ReadonlyArray<Parameters<typeof simRowBadges>[0] & Parameters<typeof simPlayerTags>[0]>): BadgeKind[] {
  return contextSuppressed(
    players.map((p) => [
      ...simRowBadges(p).map((b) => b.kind),
      ...(simPlayerTags(p) ?? []).flatMap((t) => {
        const b = badgeFromTag(t);
        return b ? [b.kind] : [];
      }),
    ]),
  );
}

/** The rookie draft's collapsed clock line: "R1 P4 · You pick now · 31 rookies left · 2 picks to make". */
export function simRookieSummaryParts(
  d: { on_clock: { round: number; n: number; team_name: string | null } | null; your_turn: boolean; total: number; pick_index: number; available_count: number },
  picksToMake: number,
): CompactPart[] {
  if (!d.on_clock) return [{ key: "done", text: d.pick_index >= d.total && d.total > 0 ? "Rookie draft complete" : "Rookie draft not started", tone: d.pick_index >= d.total ? "success" : "muted", strong: true }];
  return compactParts([
    { key: "rp", text: `R${d.on_clock.round} P${d.on_clock.n}/${d.total}`, strong: true },
    d.your_turn ? { key: "state", text: "You pick now", tone: "action", strong: true } : { key: "state", text: `${d.on_clock.team_name ?? "An AI team"} is up` },
    { key: "left", text: `${d.available_count} rookie${d.available_count === 1 ? "" : "s"} left` },
    picksToMake > 0 ? { key: "mine", text: `${picksToMake} pick${picksToMake === 1 ? "" : "s"} to make`, tone: "warning" } : null,
  ]);
}

interface SimRookieOrderLike {
  n: number;
  round: number;
  pick: string;
  is_yours: boolean;
  made: { id: string; name: string; pos: string } | null;
}

/** The rookie draft as the same mini board cells (rounds of picks; the pick on the clock ringed). */
export function simRookieMiniBoard(order: readonly SimRookieOrderLike[], onClockPick: string | null | undefined): SimMiniCell[][] {
  const rounds = new Map<number, SimMiniCell[]>();
  for (const row of order) {
    const cells = rounds.get(row.round) ?? [];
    cells.push({ key: row.pick, pos: row.made?.pos ?? null, you: row.is_yours, clock: !row.made && row.pick === onClockPick, pickNo: row.n });
    rounds.set(row.round, cells);
  }
  return [...rounds.entries()].sort((a, b) => a[0] - b[0]).map(([, cells]) => cells);
}

/** Latest made rookie picks as recent-strip chips, newest first. */
export function simRookieRecentChips(order: readonly SimRookieOrderLike[], count = 8): { key: string; label: string; pos: string }[] {
  return order
    .filter((o) => o.made)
    .sort((a, b) => b.n - a.n)
    .slice(0, count)
    .map((o) => {
      const parts = o.made!.name.trim().split(/\s+/);
      return { key: o.pick, label: `#${o.n} ${parts[parts.length - 1]} ${o.made!.pos}`, pos: o.made!.pos };
    });
}

/**
 * The pinned draft bar's second line (V1 with the avatar): the best available player with his avatar, position and
 * letter grade. Never a number for the model's rating: the grade is a letter, ADP and projection are the only figures.
 */
export interface SimDraftBarModel {
  playerId: string | null;
  name: string;
  position: string;
  team: string | null;
  /** "ADP 5" or null. */
  adp: string | null;
  /** A letter ("A-"), or null when the game has no grade for him. */
  grade: string | null;
  /** "Fills your RB need" when his position is a starter slot you have not filled. */
  fit: string | null;
}

export function simDraftBarModel(
  player: Pick<SimGamePlayer, "name" | "pos" | "team" | "adp"> & { headshot_id?: string | null; grade?: string | null },
  needs: readonly SimDraftNeed[],
): SimDraftBarModel {
  const need = needs.find((n) => n.pos === player.pos && n.starters > 0 && n.have < n.starters);
  return {
    playerId: player.headshot_id ?? null,
    name: player.name,
    position: player.pos,
    team: player.team,
    adp: player.adp != null && !Number.isNaN(player.adp) ? `ADP ${simFmtValue(player.adp)}` : null,
    grade: player.grade ?? null,
    fit: need ? `Fills your ${need.pos} need` : null,
  };
}

/**
 * One card of the recent-picks strip in the pinned clock area: the player (avatar + name + position + letter grade) and the team
 * that took him (its generated logo via SimTeamIdentity). Public facts only: no rating, no value.
 */
export interface SimRecentPickCard {
  key: string;
  pickNo: number;
  /** "#12" (redraft) or the rookie slot label. */
  pickLabel: string;
  player: { id: string; name: string; position: string; team: string | null; headshotId: string | null };
  grade: SimGradeInput | null;
  /** The picking team's name (for its logo), or null when the source does not say. */
  teamName: string | null;
  isYou: boolean;
  aria: string;
}

/** The last `count` picks of the redraft, newest first, with the team that made each one. */
export function simRecentPickCards(draft: Pick<SimDraftState, "picks" | "teams">, count = 6): SimRecentPickCard[] {
  const teams = new Map((draft.teams ?? []).map((t) => [t.team_id, t]));
  return simDraftRecentPicks(draft.picks, count).map((pk) => {
    const team = teams.get(pk.team_id);
    return {
      key: String(pk.pick_no),
      pickNo: pk.pick_no,
      pickLabel: `#${pk.pick_no}`,
      player: { id: pk.player.id, name: pk.player.name, position: pk.player.pos, team: pk.player.team ?? null, headshotId: simHeadshotId(pk.player) },
      grade: simGradeOf(pk.player),
      teamName: team?.name ?? null,
      isYou: Boolean(team?.is_you),
      aria: `Pick ${pk.pick_no}: ${pk.player.name}, ${pk.player.pos}${team ? `, taken by ${team.name}` : ""}. Open player details`,
    };
  });
}

/** The last rookie-draft picks as the same cards (the rookie order names the player but not the team or a grade). */
export function simRookieRecentCards(order: readonly SimRookieOrderLike[], count = 6): SimRecentPickCard[] {
  return order
    .filter((o) => o.made)
    .sort((a, b) => b.n - a.n)
    .slice(0, count)
    .map((o) => ({
      key: o.pick,
      pickNo: o.n,
      pickLabel: o.pick || `#${o.n}`,
      player: { id: o.made!.id, name: o.made!.name, position: o.made!.pos, team: null, headshotId: /^\d+$/.test(o.made!.id) ? o.made!.id : null },
      grade: null,
      teamName: null,
      isYou: o.is_yours,
      aria: `Pick ${o.pick}: ${o.made!.name}, ${o.made!.pos}`,
    }));
}

export interface SimSurvivalEntry {
  name: string;
  pos: string;
  /** His position is a starter slot you have not filled. */
  need: boolean;
}

export interface SimSurvival {
  /** Your next pick number and how many picks come before it. */
  nextPickNo: number;
  picksAway: number;
  /** Public ADP says he is normally off the board by then. */
  gone: SimSurvivalEntry[];
  /** Close to the line: could go either way. */
  toss: SimSurvivalEntry[];
  /** ADP says he should still be there. */
  there: SimSurvivalEntry[];
  /** A position that is running (3+ of the last 6 picks), which makes its players less likely to last. */
  run: { pos: string; count: number } | null;
  /** One sentence for the module. */
  text: string;
}

/**
 * "Who survives to my pick": from PUBLIC information only. Factors: your next pick and how many picks come first, each
 * target's public ADP against that line, a position run in the last six picks (the AI is taking that position now), and
 * which positions you still need (needs come first). It never reads the model's value or rating. Null when there is
 * nothing honest to say (you are on the clock, the draft is over, you have no pick left, or no target has an ADP).
 */
export function simDraftSurvival(
  draft: Pick<SimDraftState, "status" | "pick_no" | "your_pick_numbers" | "on_the_clock" | "picks">,
  targets: ReadonlyArray<Pick<SimGamePlayer, "name" | "pos" | "adp">>,
  needs: readonly SimDraftNeed[],
  opts: { max?: number } = {},
): SimSurvival | null {
  const max = opts.max ?? 3;
  if (draft.status !== "in_progress" || draft.on_the_clock?.is_you) return null;
  const nextPickNo = [...(draft.your_pick_numbers ?? [])].sort((a, b) => a - b).find((n) => n > draft.pick_no) ?? null;
  if (nextPickNo == null) return null;
  const picksAway = nextPickNo - draft.pick_no;
  const recent = simDraftRecentPicks(draft.picks, 6);
  const counts = new Map<string, number>();
  for (const pk of recent) counts.set(pk.player.pos, (counts.get(pk.player.pos) ?? 0) + 1);
  const top = [...counts.entries()].sort((a, b) => b[1] - a[1])[0];
  const run = top && top[1] >= 3 ? { pos: top[0], count: top[1] } : null;
  const needy = new Set(needs.filter((n) => n.starters > 0 && n.have < n.starters).map((n) => n.pos));
  const seen = new Set<string>();
  const entries: { entry: SimSurvivalEntry; adp: number }[] = [];
  for (const t of targets) {
    if (t.adp == null || Number.isNaN(t.adp) || seen.has(t.name)) continue;
    seen.add(t.name);
    entries.push({ entry: { name: playerSurname(t.name), pos: t.pos, need: needy.has(t.pos) }, adp: t.adp });
  }
  if (entries.length === 0) return null;
  // Needs first, then the better ADP.
  entries.sort((a, b) => Number(b.entry.need) - Number(a.entry.need) || a.adp - b.adp);
  const picked = entries.slice(0, max);
  const gone: SimSurvivalEntry[] = [];
  const toss: SimSurvivalEntry[] = [];
  const there: SimSurvivalEntry[] = [];
  for (const { entry, adp } of picked) {
    // A running position makes its players go about three picks ahead of their ADP.
    const effective = adp - (run && run.pos === entry.pos ? 3 : 0);
    const line = nextPickNo - 1;
    if (effective <= line - 2) gone.push(entry);
    else if (effective <= line + 3) toss.push(entry);
    else there.push(entry);
  }
  const names = (xs: SimSurvivalEntry[]) => xs.map((x) => `${x.name} (${x.pos})`).join(", ");
  const bits = [
    gone.length ? `likely gone: ${names(gone)}` : null,
    toss.length ? `could go either way: ${names(toss)}` : null,
    there.length ? `likely there: ${names(there)}` : null,
  ].filter(Boolean);
  const head = `${picksAway} pick${picksAway === 1 ? "" : "s"} before your #${nextPickNo}`;
  const runBit = run ? ` ${run.pos} run: ${run.count} of the last ${recent.length}.` : "";
  return { nextPickNo, picksAway, gone, toss, there, run, text: `${head}, ${bits.join("; ")}.${runBit}` };
}
