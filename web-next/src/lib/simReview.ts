/**
 * Season in Review: a typed, data-driven list of recap sections.
 *
 * The Fantasy Sim final grade page renders `ReviewSection[]`; the real-league
 * yearly summary will feed the same section components by mapping its own data
 * into the same list (see docs/season-in-review-sections.md). Nothing here is
 * specific to the sim except `buildSimReviewSections`, which maps the backend
 * `review` payload (modules/sim/game_review.py) and `decisions_that_mattered`.
 *
 * Web and mobile hold a byte-identical copy of this file
 * (scripts/check_lib_twins.mjs), so it has no imports. Every input field is
 * optional: an older stored result has no `review`, and a malformed value is
 * skipped rather than thrown on.
 */

export type ReviewTone = "success" | "accent" | "warning" | "danger" | "muted";

/** One glyph per kind of card or section; each renderer draws its own icon from this key. */
export type ReviewGlyph =
  | "lineup" | "waiver" | "trade" | "draft" | "injury" | "boom" | "bust"
  | "game" | "trophy" | "rank" | "leader" | "stats" | "path";

export interface ReviewPlayer {
  id: string;
  name: string;
  pos: string;
  team?: string | null;
  headshot_id?: string | null;
  /** get / give / add / drop / pick / hurt / bench / started: how the player figures in the card. */
  role?: string;
  status?: "out" | null;
}

export interface ReviewDelta {
  text: string;
  tone: ReviewTone;
}

export interface ReviewChip {
  label: string;
  tone: ReviewTone;
}

export interface ReviewCard {
  id: string;
  glyph: ReviewGlyph;
  tone: ReviewTone;
  /** Small uppercase kind label ("Best trade"). */
  label: string;
  headline: string;
  players: ReviewPlayer[];
  delta?: ReviewDelta | null;
  detail?: string;
  chip?: ReviewChip | null;
}

export interface ReviewStat {
  label: string;
  value: string;
  sub?: string;
  tone: ReviewTone;
  player?: ReviewPlayer | null;
}

export interface ReviewPathStep {
  label: string;
  sub?: string;
  /** "win" | "loss" | "bye" colors the node. */
  result: "win" | "loss" | "bye";
  score?: string;
}

export interface ReviewJourneyPoint {
  label: string;
  rank: number;
  sub?: string;
}

export interface ReviewLeaderRow {
  player: ReviewPlayer;
  value: string;
  sub?: string;
  highlight?: boolean;
}

export interface ReviewLeaderGroup {
  title: string;
  /** Position code when the group is a position (drives the position badge). */
  pos?: string;
  rows: ReviewLeaderRow[];
}

export interface ReviewGameRow {
  label: string;
  sub?: string;
  score: string;
  tone: ReviewTone;
  chip?: ReviewChip | null;
}

interface SectionBase {
  id: string;
  title: string;
  note?: string;
  glyph: ReviewGlyph;
}

export type ReviewSection =
  | (SectionBase & { kind: "stats"; items: ReviewStat[] })
  | (SectionBase & { kind: "cards"; cards: ReviewCard[] })
  | (SectionBase & { kind: "path"; steps: ReviewPathStep[]; caption?: string })
  | (SectionBase & { kind: "journey"; points: ReviewJourneyPoint[]; teams: number })
  | (SectionBase & { kind: "leaders"; groups: ReviewLeaderGroup[] })
  | (SectionBase & { kind: "games"; rows: ReviewGameRow[] });

// ---------------------------------------------------------------------------
// Tolerant readers

type Obj = Record<string, unknown>;

function obj(value: unknown): Obj | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Obj) : null;
}
function arr(value: unknown): Obj[] {
  return Array.isArray(value) ? (value.filter((v) => obj(v)) as Obj[]) : [];
}
function str(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : typeof value === "number" && Number.isFinite(value) ? String(value) : fallback;
}
function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function reviewPlayer(raw: unknown): ReviewPlayer | null {
  const o = obj(raw);
  if (!o || o.id == null || !o.name) return null;
  return {
    id: String(o.id),
    name: str(o.name),
    pos: str(o.pos),
    team: typeof o.team === "string" ? o.team : null,
    headshot_id: typeof o.headshot_id === "string" ? o.headshot_id : null,
    role: typeof o.role === "string" ? o.role : undefined,
  };
}

function players(raw: unknown): ReviewPlayer[] {
  return Array.isArray(raw) ? (raw.map(reviewPlayer).filter(Boolean) as ReviewPlayer[]) : [];
}

// ---------------------------------------------------------------------------
// Formatting

/** One decimal, trailing ".0" dropped: 12 -> "12", 12.34 -> "12.3". */
export function reviewFmt(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}

export function reviewToneForSign(value: number, threshold = 0): ReviewTone {
  return value > threshold ? "success" : value < -threshold ? "danger" : "muted";
}

/** "+12.3 pts" / "-4 pts" with the tone that matches its sign. */
export function reviewSignedDelta(value: number, unit: string): ReviewDelta {
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return { text: `${sign}${reviewFmt(Math.abs(value))} ${unit}`.trim(), tone: reviewToneForSign(value) };
}

function ordinal(n: number): string {
  const v = n % 100;
  if (v >= 11 && v <= 13) return `${n}th`;
  return `${n}${({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th"}`;
}

function deltaFor(raw: unknown): ReviewDelta | null {
  const d = obj(raw);
  const value = d ? num(d.value) : null;
  if (!d || value == null) return null;
  const unit = str(d.unit);
  if (unit === "adp") return { text: `${value >= 0 ? "+" : "-"}${reviewFmt(Math.abs(value))} vs ADP`, tone: reviewToneForSign(value) };
  if (unit === "ppg") return { text: `${reviewFmt(value)} pts/game`, tone: "warning" };
  return reviewSignedDelta(value, unit || "pts");
}

const AWARD_GLYPH: Record<string, ReviewGlyph> = {
  trade: "trade", waiver: "waiver", draft: "draft", boom: "boom", bust: "bust", injury: "injury", lineup: "lineup",
};

// ---------------------------------------------------------------------------
// Decisions that mattered

/** A decision from the backend (`decisions_that_mattered`) as a card. */
export function reviewDecisionCard(raw: unknown, index: number): ReviewCard | null {
  const d = obj(raw);
  if (!d || (!d.title && !d.detail)) return null;
  const kind = str(d.kind, "trade");
  const impact = obj(d.impact);
  const value = impact ? num(impact.season_value) : null;
  const wins = impact ? num(impact.wins) : null;
  const ppg = impact ? num(impact.points_per_game) : null;
  let delta: ReviewDelta | null = null;
  if (kind === "lineup") {
    const left = /(\d+(?:\.\d+)?) points sat/.exec(str(d.title));
    delta = left ? { text: `-${left[1]} pts`, tone: "danger" } : null;
  } else if (wins != null && ppg != null) {
    delta = { text: `${wins > 0 ? "+" : wins < 0 ? "-" : ""}${reviewFmt(Math.abs(wins))} W · ${ppg >= 0 ? "+" : "-"}${reviewFmt(Math.abs(ppg))} PPG`, tone: reviewToneForSign(value ?? wins, 0.1) };
  }
  const tone: ReviewTone = kind === "lineup" ? "warning" : value == null ? "accent" : value >= 0.25 ? "success" : value <= -0.25 ? "danger" : "muted";
  const outcomeRaw = str(impact?.playoff_result_with);
  const outcomeLabel: Record<string, string> = {
    champion: "Won the title", runner_up: "Runner-up", semifinal: "Semifinals", missed: "Missed playoffs",
    lost_round_1: "Out in round 1", lost_round_2: "Out in round 2", lost_round_3: "Out in round 3",
  };
  const outcome = outcomeRaw ? outcomeLabel[outcomeRaw] ?? outcomeRaw.replace(/_/g, " ") : "";
  return {
    id: `decision-${index}`,
    glyph: AWARD_GLYPH[kind] ?? "trade",
    tone,
    label: kind === "lineup" ? "Lineup" : kind === "waiver" ? "Waiver" : kind === "trade" ? "Trade" : kind.replace(/_/g, " "),
    headline: str(d.title),
    players: players(d.players),
    delta,
    detail: str(d.detail),
    chip: kind !== "lineup" && outcome ? { label: outcome, tone: outcomeRaw === "champion" ? "success" : outcomeRaw === "missed" ? "danger" : "accent" } : null,
  };
}

// ---------------------------------------------------------------------------
// Builders (one per section)

function awardCard(raw: Obj, index: number): ReviewCard | null {
  if (!raw.headline && !raw.label) return null;
  const kind = str(raw.kind);
  const tone: ReviewTone = raw.tone === "good" ? "success" : raw.tone === "bad" ? "danger" : "accent";
  const outcome = str(raw.outcome);
  return {
    id: str(raw.key, `award-${index}`),
    glyph: AWARD_GLYPH[kind] ?? "stats",
    tone,
    label: str(raw.label),
    headline: str(raw.headline),
    players: players(raw.players),
    delta: deltaFor(raw.delta),
    detail: str(raw.detail),
    chip: outcome ? { label: outcome, tone } : null,
  };
}

function statItems(raw: unknown): ReviewStat[] {
  return arr(raw).map((s) => ({
    label: str(s.label),
    value: str(s.value),
    sub: str(s.sub) || undefined,
    tone: (s.tone === "good" ? "success" : s.tone === "bad" ? "danger" : "muted") as ReviewTone,
    player: reviewPlayer(s.player),
  })).filter((s) => s.label && s.value);
}

function pathSteps(raw: unknown): ReviewPathStep[] {
  const path = obj(raw);
  if (!path) return [];
  const total = num(path.total_rounds) ?? 0;
  return arr(path.rounds).map((r) => {
    const round = num(r.round) ?? 0;
    const name = total && round === total ? "Final" : total && round === total - 1 && total >= 2 ? "Semifinal" : `Round ${round}`;
    if (r.bye) return { label: name, sub: "First-round bye", result: "bye" as const };
    const won = r.won === true;
    const seed = num(r.opponent_seed);
    return {
      label: name,
      sub: `vs ${str(r.opponent, "opponent")}${seed ? ` (#${seed} seed)` : ""}`,
      result: won ? ("win" as const) : ("loss" as const),
      score: `${reviewFmt(num(r.pts) ?? 0)}-${reviewFmt(num(r.opp_pts) ?? 0)}`,
    };
  });
}

function gameRow(g: Obj, youId?: boolean): ReviewGameRow {
  const home = str(g.home);
  const away = str(g.away);
  const yours = g.is_yours === true || youId === true;
  const won = g.you_won === true;
  const lost = g.you_won === false;
  const phase = g.kind === "playoff" ? "Playoffs" : "Week";
  return {
    label: `${home} vs ${away}`,
    sub: `${phase} ${num(g.week) ?? ""}`.trim() + (num(g.margin) != null ? ` · decided by ${reviewFmt(num(g.margin) as number)}` : ""),
    score: `${reviewFmt(num(g.home_pts) ?? 0)}-${reviewFmt(num(g.away_pts) ?? 0)}`,
    tone: yours ? (won ? "success" : lost ? "danger" : "muted") : "muted",
    chip: yours ? { label: won ? "You won" : lost ? "You lost" : "You tied", tone: won ? "success" : lost ? "danger" : "muted" } : null,
  };
}

/** The sim's finished-game sections, in page order. Pure; tolerates a missing `review`. */
export function buildSimReviewSections(input: { decisions?: unknown; review?: unknown; components?: unknown }): ReviewSection[] {
  const out: ReviewSection[] = [];
  const review = obj(input.review) ?? {};

  const parts: ReviewStat[] = arr(input.components).map((c) => {
    const score = num(c.score);
    const weight = num(c.weight);
    return {
      label: str(c.label), value: score == null ? "" : String(Math.round(score)),
      sub: weight == null ? undefined : `${Math.round(weight * 100)}% of grade`,
      tone: score == null ? "muted" : score >= 70 ? "success" : score >= 45 ? "warning" : "danger",
    } as ReviewStat;
  }).filter((s) => s.label && s.value);
  if (parts.length) out.push({ id: "grade", kind: "stats", glyph: "trophy", title: "How your grade was built", note: "Each part is scored 0 to 100.", items: parts });

  const stats = statItems(review.season_stats);
  if (stats.length) out.push({ id: "stats", kind: "stats", glyph: "stats", title: "Your season by the numbers", items: stats });

  const decisions = (Array.isArray(input.decisions) ? input.decisions : []).map(reviewDecisionCard).filter(Boolean) as ReviewCard[];
  if (decisions.length) {
    out.push({ id: "decisions", kind: "cards", glyph: "lineup", title: "Decisions that mattered",
      note: "The moves that moved your season most, from replaying it without them.", cards: decisions });
  }

  const awards = arr(review.awards).map(awardCard).filter(Boolean) as ReviewCard[];
  const pick = (kinds: string[]) => awards.filter((a) => kinds.includes(a.glyph));
  const moves = pick(["trade", "waiver", "draft"]);
  if (moves.length) out.push({ id: "moves", kind: "cards", glyph: "trade", title: "Trades, waivers and the draft", cards: moves });
  const swings = pick(["boom", "bust"]);
  if (swings.length) out.push({ id: "swings", kind: "cards", glyph: "boom", title: "Boom and bust", cards: swings });

  const inj = obj(review.injuries);
  const injCards = pick(["injury"]);
  if (injCards.length || (inj && (num(inj.your_injuries) ?? 0) > 0)) {
    const injStats: ReviewStat[] = [];
    if (inj) {
      injStats.push({ label: "Your injuries", value: str(inj.your_injuries, "0"), tone: "danger" });
      injStats.push({ label: "Weeks missed", value: str(inj.weeks_missed, "0"), tone: "danger" });
      injStats.push({ label: "Points lost", value: reviewFmt(num(inj.points_lost) ?? 0), tone: "danger" });
      const worst = obj(inj.most_injured_team);
      if (worst && worst.name) injStats.push({ label: "Most banged-up team", value: str(worst.name), sub: `${str(worst.count)} injuries${worst.is_you ? " (you)" : ""}`, tone: "warning" });
    }
    out.push({ id: "injuries", kind: "cards", glyph: "injury", title: "Injuries", cards: injCards,
      note: injStats.map((s) => `${s.label}: ${s.value}`).join(" · ") || undefined });
  }

  const champ = obj(review.champion_path);
  const champSteps = pathSteps(champ);
  if (champ && champSteps.length) {
    out.push({ id: "champion-path", kind: "path", glyph: "trophy", title: "Champion path", steps: champSteps,
      caption: `${str(champ.name)}${champ.is_you ? " (you)" : ""}, the #${num(champ.seed) ?? "?"} seed` });
  }
  const mine = obj(review.your_path);
  const mineSteps = pathSteps(mine);
  if (mine && mineSteps.length) {
    out.push({ id: "your-path", kind: "path", glyph: "path", title: "Your playoff run", steps: mineSteps,
      caption: `The #${num(mine.seed) ?? "?"} seed` });
  }

  const journey = arr(review.rank_journey).map((r) => ({
    label: `W${num(r.week) ?? ""}`, rank: num(r.rank) ?? 0, sub: `${str(r.wins)}-${str(r.losses)}${num(r.ties) ? `-${str(r.ties)}` : ""}`,
  })).filter((p) => p.rank > 0);
  if (journey.length > 1) {
    const teams = num(review.team_count) ?? Math.max(...journey.map((p) => p.rank));
    const first = journey[0].rank;
    const last = journey[journey.length - 1].rank;
    out.push({ id: "journey", kind: "journey", glyph: "rank", title: "Standings journey", teams, points: journey,
      note: `${ordinal(first)} after week 1, ${ordinal(last)} at the end of the regular season.` });
  }

  const leaders = obj(review.leaders);
  const groups: ReviewLeaderGroup[] = [];
  for (const g of arr(leaders?.league)) {
    const rows = arr(g.rows).map((r): ReviewLeaderRow | null => {
      const player = reviewPlayer(r.player);
      return player ? { player, value: `${reviewFmt(num(r.pts) ?? 0)} pts`, sub: `${reviewFmt(num(r.ppg) ?? 0)} ppg · ${str(r.team_name)}`, highlight: r.is_you === true } : null;
    }).filter(Boolean) as ReviewLeaderRow[];
    if (rows.length) groups.push({ title: str(g.pos), pos: str(g.pos), rows });
  }
  if (groups.length) out.push({ id: "leaders", kind: "leaders", glyph: "leader", title: "League stat leaders", note: "Top scorers by position over the whole season.", groups });

  const yours: ReviewLeaderGroup[] = [];
  for (const g of arr(leaders?.yours)) {
    const rows = arr(g.rows).map((r): ReviewLeaderRow | null => {
      const player = reviewPlayer(r.player);
      return player ? { player, value: str(r.value) } : null;
    }).filter(Boolean) as ReviewLeaderRow[];
    if (rows.length) yours.push({ title: str(g.label), rows });
  }
  if (yours.length) out.push({ id: "your-leaders", kind: "leaders", glyph: "leader", title: "Your team's stat leaders", groups: yours });

  const games = obj(review.games);
  const closest = arr(games?.closest_yours).map((g) => gameRow(g));
  if (closest.length) out.push({ id: "closest-yours", kind: "games", glyph: "game", title: "Your closest games", rows: closest });
  const league = arr(games?.closest_league).map((g) => gameRow(g));
  if (league.length) out.push({ id: "closest-league", kind: "games", glyph: "game", title: "Closest games in the league", rows: league });

  return out;
}

/** The plain-text share summary: grade line plus the headline award from each kind. */
export function reviewShareLines(sections: readonly ReviewSection[], max = 4): string[] {
  const lines: string[] = [];
  for (const s of sections) {
    if (s.kind !== "cards" || s.id === "decisions") continue;
    for (const c of s.cards) {
      if (lines.length >= max) return lines;
      const who = c.players[0]?.name;
      lines.push(`${c.label}: ${who ? `${who}, ` : ""}${c.delta ? c.delta.text : c.headline}`);
    }
  }
  return lines;
}

// ---------------------------------------------------------------------------
// Share card model (the same model feeds the web Satori card and the app's captured card)

export type ReviewOutcome = "champion" | "runner_up" | "playoffs" | "missed" | "none";

/** Which of the four headline results a playoff_result key means. */
export function reviewOutcome(playoffResult: string | null | undefined, isChampion = false): ReviewOutcome {
  if (isChampion || playoffResult === "champion") return "champion";
  if (!playoffResult) return "none";
  if (playoffResult === "runner_up") return "runner_up";
  if (playoffResult === "missed") return "missed";
  return "playoffs";
}

export const REVIEW_OUTCOME_TITLE: Record<ReviewOutcome, string> = {
  champion: "League Champion",
  runner_up: "Runner-up",
  playoffs: "Made the playoffs",
  missed: "Missed the playoffs",
  none: "Season complete",
};

/** "A-" -> { base: "A", modifier: "-" }: the card draws the modifier as its own small glyph. */
export function splitReviewGrade(letter: string | null | undefined): { base: string; modifier: "+" | "-" | "" } {
  const text = (letter ?? "").trim().replace(/[\u2212\u2013\u2014]/g, "-");
  const match = /^([A-Za-z])\s*([+-]?)/.exec(text);
  if (!match) return { base: text ? text.slice(0, 1) : "-", modifier: "" };
  return { base: match[1].toUpperCase(), modifier: match[2] as "+" | "-" | "" };
}

/** Facts from the backend grade summary object (record, finish, ranks); anything else is ignored. */
export function reviewSummaryFacts(summary: unknown): { record: string; finish: number | null; pointsRank: number | null; efficiencyPct: number | null; draftGrade: string } {
  const o = obj(summary);
  return {
    record: o ? str(o.record) : "",
    finish: o ? num(o.finish) : null,
    pointsRank: o ? num(o.points_rank) : null,
    efficiencyPct: o && num(o.lineup_efficiency) != null ? Math.round((num(o.lineup_efficiency) as number) * 100) : null,
    draftGrade: o ? str(o.draft_grade) : "",
  };
}

/** The Sleeper headshot id the card fetches (null: draw initials). */
export function reviewHeadshotId(p: Pick<ReviewPlayer, "id" | "headshot_id">): string | null {
  if (p.headshot_id) return p.headshot_id;
  return /^\d+$/.test(p.id) ? p.id : null;
}

export interface ReviewShareHighlight {
  label: string;
  text: string;
  delta?: string;
  tone: ReviewTone;
  glyph: ReviewGlyph;
  player: { name: string; pos: string; team: string; headshotId: string | null } | null;
}

export interface ReviewShareModel {
  /** Header kicker, "Season in Review". */
  title: string;
  letter: string;
  gradeTone: ReviewTone;
  teamName: string;
  outcome: ReviewOutcome;
  /** The outcome title: "League Champion", "Runner-up", ... */
  headline: string;
  /** Record and finish, e.g. "7-6-1 · Finished 6th · 2nd in points". */
  subline: string;
  record: string;
  /** Extra true numbers under the subline: lineup efficiency, draft grade, who won the title. */
  tags: string[];
  highlights: ReviewShareHighlight[];
  stats: { label: string; value: string }[];
}

export function buildReviewShareModel(input: {
  title?: string;
  letter: string;
  gradeTone: ReviewTone;
  teamName?: string;
  /** Raw playoff_result key from the standings row. */
  playoffResult?: string | null;
  isChampion?: boolean;
  record?: string;
  /** Regular-season finish when the grade summary has none. */
  finish?: number | null;
  /** Raw grade.summary (object from the backend). */
  summary?: unknown;
  championName?: string | null;
  /** Overrides the outcome title / the record line. */
  headline?: string;
  subline?: string;
  sections: readonly ReviewSection[];
}): ReviewShareModel {
  const highlights: ReviewShareModel["highlights"] = [];
  const stats: ReviewShareModel["stats"] = [];
  for (const s of input.sections) {
    if (s.kind === "stats" && s.id === "stats" && stats.length === 0) {
      for (const i of s.items.slice(0, 4)) stats.push({ label: i.label, value: i.value });
    }
    if (s.kind === "cards" && s.id !== "decisions") {
      for (const c of s.cards) {
        if (highlights.length >= 4) break;
        const p = c.players[0];
        highlights.push({
          label: c.label,
          text: p?.name ?? c.headline,
          delta: c.delta?.text,
          tone: c.tone,
          glyph: c.glyph,
          player: p ? { name: p.name, pos: p.pos, team: p.team ?? "", headshotId: reviewHeadshotId(p) } : null,
        });
      }
    }
  }
  const outcome = reviewOutcome(input.playoffResult, input.isChampion);
  const facts = reviewSummaryFacts(input.summary);
  const record = input.record || facts.record;
  const finish = facts.finish ?? input.finish ?? null;
  const subline =
    input.subline ??
    [record, finish != null ? `Finished ${ordinal(finish)}` : "", facts.pointsRank != null ? `${ordinal(facts.pointsRank)} in points` : ""].filter(Boolean).join(" \u00b7 ");
  const tags = [
    facts.efficiencyPct != null ? `${facts.efficiencyPct}% lineup efficiency` : "",
    facts.draftGrade ? `Draft grade ${facts.draftGrade}` : "",
    outcome !== "champion" && input.championName ? `${input.championName} won the title` : "",
  ].filter(Boolean);
  return {
    title: input.title ?? "Season in Review",
    letter: input.letter,
    gradeTone: input.gradeTone,
    teamName: input.teamName ?? "",
    outcome,
    headline: input.headline ?? REVIEW_OUTCOME_TITLE[outcome],
    subline,
    record,
    tags,
    highlights,
    stats,
  };
}
