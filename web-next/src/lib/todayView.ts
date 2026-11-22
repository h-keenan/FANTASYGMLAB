/**
 * The rebuilt Today page's pure models (docs/ui-patterns.md, "Today"): the matchup ring card, the "Do this now" swap
 * stack, the Standing / Playoffs / Trades tiles and the position-room chips. Every figure is read from a response the
 * page already has (lib/teamStatus.ts, lib/decisionQueue.ts); nothing is estimated here, and a fact lives in exactly one
 * of these models so it is never drawn twice. Import-light, byte-identical twin of mobile/src/lib/todayView.ts.
 */
import { playerSurname } from "./playerNameDisplay.ts";
import { bandSimTone, percentBand } from "./verdictTone.ts";
import type { Decision, DecisionPlayer, DecisionSwap, DecisionTone } from "./decisionQueue";
import type { TeamStatusMatchup, TeamStatusPosition, TeamStatusStanding } from "./teamStatus";

type Tone = "success" | "danger" | "warning" | "accent" | "muted";

const round1 = (n: number): number => Math.round(n * 10) / 10;

// ---------------------------------------------------------------------------------------------------------------------
// Matchup ring card
// ---------------------------------------------------------------------------------------------------------------------

export interface TodayMatchupRing {
  /** Win chance 0-100; null when the model has no honest number (the ring is then an empty track). */
  pct: number | null;
  tone: Tone;
  /** "WK 10 · VS SHIESTY" (with " · LIVE" / " · FINAL" when games are on). */
  kicker: string;
  /** "109.7 vs 136.9": real points once games started, else the projections. Null when neither exists. */
  scoreLine: string | null;
  /** "projected" / "live" / "final". */
  scoreCaption: string | null;
  /** "trailing 27.2" / "leading 5.0"; null when level or unknown. */
  chip: { label: string; tone: "success" | "danger" } | null;
}

export function todayMatchupRing(m: TeamStatusMatchup): TodayMatchupRing {
  const week = m.week != null ? `WK ${m.week}` : "THIS WEEK";
  const state = m.stateLabel ? ` · ${m.stateLabel.toUpperCase()}` : "";
  const mine = m.live ? m.live.mine : m.myProjected;
  const theirs = m.live ? m.live.opponent : m.opponentProjected;
  const known = mine != null && theirs != null;
  const diff = known ? round1((mine as number) - (theirs as number)) : 0;
  const pct = m.winPercent;
  return {
    pct,
    tone: pct == null ? "muted" : bandSimTone(percentBand(pct)),
    kicker: `${week} · VS ${m.opponentName.toUpperCase()}${state}`,
    scoreLine: known ? `${(mine as number).toFixed(1)} vs ${(theirs as number).toFixed(1)}` : null,
    scoreCaption: known ? (m.stateLabel === "Final" ? "final" : m.live ? "live" : "projected") : null,
    chip: known && Math.abs(diff) >= 0.1 ? { label: `${diff < 0 ? "trailing" : "leading"} ${Math.abs(diff).toFixed(1)}`, tone: diff < 0 ? "danger" : "success" } : null,
  };
}

// ---------------------------------------------------------------------------------------------------------------------
// "Do this now": swap rows and the Fix-all button
// ---------------------------------------------------------------------------------------------------------------------

export interface TodayFixAll {
  count: number;
  /** Sum of the swaps' projected gains; null when none has one. */
  total: number | null;
  label: string;
}

/** "Fix all 3 · +35.1 proj". Null for fewer than two swaps (the row's own Swap is the fix). */
export function todayFixAll(swaps: ReadonlyArray<Pick<DecisionSwap, "gain">>): TodayFixAll | null {
  if (swaps.length < 2) return null;
  const gains = swaps.map((s) => s.gain).filter((g): g is number => g != null && g > 0);
  const total = gains.length > 0 ? round1(gains.reduce((a, b) => a + b, 0)) : null;
  return { count: swaps.length, total, label: `Fix all ${swaps.length}${total != null ? ` · +${total.toFixed(1)} proj` : ""}` };
}

/** "+11.2" for a swap's gain; null when it has none. */
export function swapGainLabel(swap: Pick<DecisionSwap, "gain">): string | null {
  return swap.gain != null && swap.gain > 0 ? `+${swap.gain.toFixed(1)}` : null;
}

/** "start Sam Ortiz" line under a swap's player. */
export function swapReplacementLine(swap: Pick<DecisionSwap, "replacement">): string {
  return swap.replacement?.name ? `start ${swap.replacement.name}` : "needs a replacement";
}

/** What a Swap tap asks the Matchup page's lineup planner to open with. */
export type MatchupPlanRequest = { kind: "all" } | { kind: "swap"; out: string; in: string };

/** The Matchup URL's planner parameters: `plan=all` (every suggested move) or `plan=swap&out=<id>&in=<id>`. */
export function matchupPlanParams(swap: Pick<DecisionSwap, "out" | "replacement"> | null): Record<string, string> {
  const out = swap?.out?.id;
  const inId = swap?.replacement?.id;
  if (swap && out && inId) return { plan: "swap", out, in: inId };
  return { plan: "all" };
}

export function parseMatchupPlan(params: { plan?: string | null; out?: string | null; in?: string | null } | null | undefined): MatchupPlanRequest | null {
  if (!params?.plan) return null;
  if (params.plan === "swap" && params.out && params.in) return { kind: "swap", out: params.out, in: params.in };
  if (params.plan === "all" || params.plan === "swap") return { kind: "all" };
  return null;
}

// ---------------------------------------------------------------------------------------------------------------------
// "Do this now" one-line rows
// ---------------------------------------------------------------------------------------------------------------------

export interface TodayActionRow {
  key: string;
  tone: DecisionTone;
  /** The player whose avatar leads the row; null when the decision is not about one player. */
  player: DecisionPlayer | null;
  /** At most ~6 words. The full reason sits behind the row's tap. */
  reason: string;
  /** The row's one button: "Swap", "Fix all", or the decision's own primary label. */
  button: string;
}

/** First `max` words of a line, with an ellipsis when it was cut. */
export function clampWords(text: string, max: number = 6): string {
  const words = text.trim().split(/\s+/).filter(Boolean);
  if (words.length <= max) return words.join(" ");
  return `${words.slice(0, max).join(" ").replace(/[,.:;\-]+$/, "")}…`;
}


/** One queue decision as a one-line row: avatar, a short reason, one button. Lineup problems collapse into one row. */
export function todayActionRow(d: Pick<Decision, "key" | "kind" | "tone" | "title" | "players" | "swaps" | "primary">): TodayActionRow {
  if (d.kind === "lineup" && d.swaps.length > 0) {
    const first = d.swaps[0];
    if (d.swaps.length === 1) {
      const who = first.out ? playerSurname(first.out.name) : "Empty slot";
      const into = first.replacement?.name ? `, start ${playerSurname(first.replacement.name)}` : "";
      return { key: d.key, tone: d.tone, player: first.out, reason: `${who} ${first.status.toLowerCase()}${into}`, button: "Swap" };
    }
    const fix = todayFixAll(d.swaps);
    return { key: d.key, tone: d.tone, player: first.out, reason: `${d.swaps.length} lineup swaps${fix?.total != null ? ` · +${fix.total.toFixed(1)}` : ""}`, button: "Fix all" };
  }
  return { key: d.key, tone: d.tone, player: d.players[0] ?? null, reason: clampWords(d.title), button: d.primary.label };
}

// ---------------------------------------------------------------------------------------------------------------------
// Tiles: Standing / Playoffs / Trades
// ---------------------------------------------------------------------------------------------------------------------

export interface TodayTile {
  key: "standing" | "playoffs" | "rank";
  label: string;
  value: string;
  sub: string;
  tone: Tone;
}

/** "8th of 12" -> { rank: "8th", of: "of 12" }; anything else is left whole. */
function splitPlace(place: string): { rank: string; of: string | null } {
  const m = /^(\S+)\s+(of\s+\d+)$/.exec(place);
  return m ? { rank: m[1], of: m[2] } : { rank: place, of: null };
}

/** The playoff odds figure's tone: only a number below 25% reads as a risk, "Out" is one, "Clinched" is good. */
function oddsTone(odds: string, standingTone: TeamStatusStanding["tone"]): Tone {
  if (standingTone === "positive") return "success";
  if (standingTone === "risk") return "danger";
  const n = Number.parseFloat(odds);
  if (!Number.isFinite(n)) return "muted";
  return bandSimTone(percentBand(n));
}

/**
 * The one snapshot strip: Standing, Playoffs, Team rank. Standing and Playoffs read the one standing model (so the old
 * Standing row and these tiles can never both appear); Team rank is the "this season" power rank (already formatted by
 * the caller, e.g. "#3"). The strip as a whole opens My Team. Tiles with no data are dropped, never zero-filled.
 */
export function todayTiles(input: { standing: TeamStatusStanding | null; /** Power rank text ("#3") and the league size, when known. */ teamRank?: { value: string; of: number | null } | null }): TodayTile[] {
  const tiles: TodayTile[] = [];
  const s = input.standing;
  if (s && (s.place || s.record)) {
    const place = s.place ? splitPlace(s.place) : null;
    tiles.push({
      key: "standing",
      label: "STANDING",
      value: place ? place.rank : (s.record as string),
      sub: place ? [place.of, s.record].filter(Boolean).join(" · ") : "record",
      tone: "muted",
    });
  }
  if (s?.playoffOdds) {
    tiles.push({ key: "playoffs", label: "PLAYOFFS", value: s.playoffOdds, sub: /%$/.test(s.playoffOdds) ? "odds" : "status", tone: oddsTone(s.playoffOdds, s.tone) });
  }
  const rank = input.teamRank;
  if (rank && rank.value && rank.value !== "—") {
    tiles.push({ key: "rank", label: "TEAM RANK", value: rank.value, sub: rank.of ? `of ${rank.of}` : "this season", tone: "accent" });
  }
  return tiles;
}

// ---------------------------------------------------------------------------------------------------------------------
// Position rooms
// ---------------------------------------------------------------------------------------------------------------------

export interface TodayRoomChip {
  position: string;
  label: TeamStatusPosition["label"];
  /** "!" for a room that needs help, a check for a solid one, empty otherwise (the chip's mark, not a number). */
  mark: "!" | "check" | "";
  tone: "danger" | "warning" | "success" | "muted";
  weakest: boolean;
  /** 0-1 meter fill for the expanded bars. Qualitative: it draws the label, not a measurement. */
  fill: number;
}

const ROOM_FILL: Record<TeamStatusPosition["label"], number> = { Strength: 0.92, Solid: 0.66, "Aging risk": 0.46, "Needs help": 0.28 };

export function todayRoomChips(rows: ReadonlyArray<TeamStatusPosition>): TodayRoomChip[] {
  return rows.map((row) => ({
    position: row.position,
    label: row.label,
    mark: row.label === "Needs help" ? "!" : row.label === "Strength" || row.label === "Solid" ? "check" : "",
    tone: row.tone === "risk" ? "danger" : row.tone === "warning" ? "warning" : row.tone === "positive" ? "success" : "muted",
    weakest: row.weakest,
    fill: ROOM_FILL[row.label],
  }));
}

// ---------------------------------------------------------------------------------------------------------------------
// Trade idea card
// ---------------------------------------------------------------------------------------------------------------------

export interface TodayTradeAsset {
  id: string | null;
  name: string;
  position: string | null;
  team: string | null;
  tier: string | null;
  isPick: boolean;
}

export interface TodayTradeIdea {
  /** "Get a QB from Team Iron". */
  title: string;
  send: TodayTradeAsset[];
  receive: TodayTradeAsset[];
  /** The server's value gain for you (the same figure Trade Hub leads with); null when absent. */
  gain: number | null;
}

interface TradeAssetInput {
  asset_type?: string;
  player_id?: string;
  name?: string;
  position?: string;
  team?: string;
  tier?: string;
  label?: string;
  season?: string;
  round?: string;
}

function tradeAsset(a: TradeAssetInput): TodayTradeAsset | null {
  const pick = a.asset_type === "pick";
  const name = (pick ? (a.label ?? [a.season, a.round ? `R${a.round}` : null].filter(Boolean).join(" ")) : a.name)?.trim();
  if (!name) return null;
  return { id: pick ? null : (a.player_id ?? null), name, position: pick ? null : (a.position ?? null), team: pick ? null : (a.team ?? null), tier: pick ? null : (a.tier ?? null), isPick: pick };
}

const AN_LETTERS = "AEFHILMNORSX";

/** The dashboard's trade idea as the Today card reads it; null when there is no real give/get package. */
export function todayTradeIdea(item: {
  headline: string;
  presentation?: { trade_package?: { send: ReadonlyArray<TradeAssetInput>; receive: ReadonlyArray<TradeAssetInput> }; partner_team_name?: unknown; trade_gain?: unknown } | null;
}): TodayTradeIdea | null {
  const pkg = item.presentation?.trade_package;
  if (!pkg) return null;
  const send = pkg.send.map(tradeAsset).filter((a): a is TodayTradeAsset => a != null);
  const receive = pkg.receive.map(tradeAsset).filter((a): a is TodayTradeAsset => a != null);
  if (send.length === 0 && receive.length === 0) return null;
  const partner = typeof item.presentation?.partner_team_name === "string" ? item.presentation.partner_team_name.trim() : "";
  const lead = receive.find((a) => !a.isPick && a.position) ?? null;
  const article = lead?.position && AN_LETTERS.includes(lead.position.charAt(0).toUpperCase()) ? "an" : "a";
  const title = lead?.position && partner ? `Get ${article} ${lead.position} from ${partner}` : item.headline;
  const gain = typeof item.presentation?.trade_gain === "number" && Number.isFinite(item.presentation.trade_gain) ? item.presentation.trade_gain : null;
  return { title, send, receive, gain };
}

/**
 * The one idea Today leads with: the biggest positive gain. An idea that costs the user value is never the headline
 * (and never drawn red): it is skipped, and an idea with no figure is used only when no idea has a positive gain.
 * Null when nothing qualifies (the row is then simply not drawn; Trade Hub still has every idea).
 */
export function bestTradeIdea(ideas: ReadonlyArray<TodayTradeIdea | null | undefined>): TodayTradeIdea | null {
  const real = ideas.filter((i): i is TodayTradeIdea => i != null);
  const positive = real.filter((i) => i.gain != null && i.gain > 0).sort((a, b) => (b.gain as number) - (a.gain as number));
  if (positive.length > 0) return positive[0];
  return real.find((i) => i.gain == null) ?? null;
}

/** "+450": the gain, only when positive. Never a negative or zero figure. */
export function tradeGainLabel(idea: Pick<TodayTradeIdea, "gain">): string | null {
  return idea.gain != null && idea.gain > 0 ? `+${Math.round(idea.gain).toLocaleString("en-US")}` : null;
}

// ---------------------------------------------------------------------------------------------------------------------
// Alerts one-liner
// ---------------------------------------------------------------------------------------------------------------------

export interface TodayAlertLine {
  playerId: string | null;
  name: string | null;
  position: string | null;
  team: string | null;
  tier: string | null;
  title: string;
}

/** The collapsed Alerts row: up to four distinct player avatars and the newest headline ("Reyes ruled OUT · +3 more"). */
export function todayAlertsSummary(lines: ReadonlyArray<TodayAlertLine>, max: number = 4): { avatars: TodayAlertLine[]; lead: string | null; more: number } {
  const seen = new Set<string>();
  const avatars: TodayAlertLine[] = [];
  for (const line of lines) {
    if (!line.playerId || seen.has(line.playerId)) continue;
    seen.add(line.playerId);
    avatars.push(line);
    if (avatars.length >= max) break;
  }
  return { avatars, lead: lines[0]?.title ?? null, more: Math.max(0, lines.length - 1) };
}
