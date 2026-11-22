/**
 * The rebuilt Today page's pure models (docs/ui-patterns.md, "Today"): the matchup ring card, the "Do this now" swap
 * stack, the Standing / Playoffs / Trades tiles and the position-room chips. Every figure is read from a response the
 * page already has (lib/teamStatus.ts, lib/decisionQueue.ts); nothing is estimated here, and a fact lives in exactly one
 * of these models so it is never drawn twice. Import-light, byte-identical twin of mobile/src/lib/todayView.ts.
 */
import { playerSurname } from "./playerNameDisplay.ts";
import { bandSimTone, percentBand } from "./verdictTone.ts";
import { DECISION_URGENCY } from "./decisionQueue.ts";
import type { Decision, DecisionItem, DecisionKind, DecisionPlayer, DecisionSwap, DecisionTone } from "./decisionQueue";
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
export function todayActionRow(d: Pick<Decision<DecisionItem>, "key" | "kind" | "tone" | "title" | "players" | "swaps" | "primary">): TodayActionRow {
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

// ---------------------------------------------------------------------------------------------------------------------
// Actionable Today: the matchup's best move, the ranked "Do this now" rows, roster-alert rows, the slim standing line
// ---------------------------------------------------------------------------------------------------------------------

/** The single best move for this matchup (the biggest-gain lineup fix), as one line that opens the lineup planner on it. */
export interface TodayMatchupMove {
  text: string;
  swap: DecisionSwap;
}

export function todayMatchupMove(swaps: ReadonlyArray<DecisionSwap> | null | undefined): TodayMatchupMove | null {
  const swap = (swaps ?? []).find((s) => s.replacement?.name);
  if (!swap || !swap.replacement) return null;
  const gain = swapGainLabel(swap);
  const into = playerSurname(swap.replacement.name);
  const head = swap.out ? `Start ${into} over ${playerSurname(swap.out.name)}` : `Fill an empty slot with ${into}`;
  return { text: gain ? `${head} (${gain})` : head, swap };
}

/** How many "Do this now" rows Today shows; the rest sit behind "See all" (GM Plan). */
export const TODAY_ACTION_CAP = 5;
/** Where the best trade ranks: under lineup, injuries and waivers, over generic briefing items. */
export const TRADE_ACTION_URGENCY = 55;

export type TodayActionKind = DecisionKind | "swap" | "trade";

/** One "Do this now" row: avatar + one short reason + ONE button. Exactly one of swap / decision / trade says where it goes. */
export interface TodayAction<T extends DecisionItem = DecisionItem> {
  key: string;
  kind: TodayActionKind;
  urgency: number;
  tone: DecisionTone;
  player: DecisionPlayer | null;
  reason: string;
  /** The fuller line behind the row's tap; null when the reason says it all. */
  detail: string | null;
  button: string;
  swap: DecisionSwap | null;
  decision: Decision<T> | null;
  trade: TodayTradeIdea | null;
}

function swapAction<T extends DecisionItem>(d: Pick<Decision<T>, "tone">, swap: DecisionSwap, order: number): TodayAction<T> {
  const into = swap.replacement?.name ? `, start ${playerSurname(swap.replacement.name)}` : "";
  const who = swap.out ? playerSurname(swap.out.name) : "Empty slot";
  const gain = swapGainLabel(swap);
  return {
    key: `swap:${swap.key}`,
    kind: "swap",
    // Lineup rows keep their gain order: a tiny step per row so the sort is stable and biggest-gain-first.
    urgency: DECISION_URGENCY.lineup - order * 0.001,
    tone: d.tone,
    player: swap.out,
    reason: swap.out ? `${who} ${swap.status.toLowerCase()}${into}` : `Empty slot${into}`,
    detail: [swap.reason, swap.replacement?.name ? `Start ${swap.replacement.name} instead` : null, gain ? `${gain} projected` : null].filter(Boolean).join(" · "),
    button: swap.out ? "Swap" : "Fill",
    swap,
    decision: null,
    trade: null,
  };
}

/**
 * The "Do this now" list: every lineup fix as its own row (starters who are out / on bye / injured, empty slots), the waiver
 * add, the deadline, draft and injury decisions, and the best trade to send, ranked by urgency and capped. Every row is one
 * thing the user can do. Pending trade offers and expiring claims are not in the engine's responses yet, so they are not
 * here (nothing is invented). `trade` is the idea Today leads with (null when none, or the deadline has passed).
 */
export function todayActions<T extends DecisionItem>(queue: { all: ReadonlyArray<Decision<T>> }, trade: TodayTradeIdea | null, cap: number = TODAY_ACTION_CAP): { rows: TodayAction<T>[]; all: TodayAction<T>[]; total: number } {
  const all: TodayAction<T>[] = [];
  for (const d of queue.all) {
    if (d.kind === "lineup" && d.swaps.length > 0) {
      d.swaps.forEach((swap, i) => all.push(swapAction(d, swap, i)));
      continue;
    }
    const row = todayActionRow(d);
    all.push({ key: d.key, kind: d.kind, urgency: d.urgency, tone: d.tone, player: row.player, reason: row.reason, detail: d.why ?? (d.summary && d.summary !== row.reason ? d.summary : null), button: row.button, swap: null, decision: d, trade: null });
  }
  if (trade) {
    const face = trade.receive.find((a) => !a.isPick) ?? trade.send.find((a) => !a.isPick) ?? null;
    const gain = tradeGainLabel(trade);
    all.push({
      key: "trade-idea",
      kind: "trade",
      urgency: TRADE_ACTION_URGENCY,
      tone: "accent",
      player: face ? { id: face.id, name: face.name, position: face.position, team: face.team, tier: face.tier, injuryStatus: null, note: null, stat: null } : null,
      reason: clampWords(trade.title),
      detail: [trade.send.length > 0 ? `Send ${trade.send.map((a) => a.name).join(" + ")}` : null, trade.receive.length > 0 ? `Get ${trade.receive.map((a) => a.name).join(" + ")}` : null, gain ? `${gain} value` : null].filter(Boolean).join(" · "),
      button: "Send offer",
      swap: null,
      decision: null,
      trade,
    });
  }
  all.sort((a, b) => b.urgency - a.urgency);
  return { rows: all.slice(0, cap), all, total: all.length };
}

/** The slice of an alert the Today rows read (web AlertItem and mobile AlertItem both satisfy it). */
export interface TodayAlertInput {
  alert_key: string;
  title: string | null;
  link: string | null;
  event_type: string | null;
  read: boolean;
  matched_player: string | null;
  matched_player_id: string | null;
  matched_player_position: string | null;
  matched_player_team: string | null;
  matched_player_tier: string | null;
  roster_relationship: "starter" | "bench" | "taxi" | "ir" | null;
}

export interface TodayAlertRow {
  key: string;
  alertKey: string;
  unread: boolean;
  player: DecisionPlayer;
  reason: string;
  /** "Swap" (a starter hurt or in trouble), "Lineup" (a starter's role changed), "Read" (a bench / IR / taxi player). */
  button: "Swap" | "Lineup" | "Read";
  /** Swap / Lineup open the matchup's lineup planner; Read opens the story. */
  target: "matchup" | "link";
  link: string | null;
  tone: "danger" | "warning" | "accent";
}

/**
 * Alerts on Today are about YOUR players only: news with no rostered player behind it never appears. A starter's injury or
 * off-field trouble reads "Swap"; a starter's role change "Lineup"; a bench / IR / taxi player's news "Read" (only when
 * there is a story to open). Starters first, unread first, then the feed's own (newest-first) order.
 */
export function todayAlertRows(items: ReadonlyArray<TodayAlertInput>, max: number = 3): { rows: TodayAlertRow[]; total: number } {
  const rows: TodayAlertRow[] = [];
  const seen = new Set<string>();
  for (const a of items) {
    if (!a.matched_player_id || !a.roster_relationship || !a.title) continue;
    if (seen.has(a.matched_player_id)) continue;
    const starter = a.roster_relationship === "starter";
    if (!starter && !a.link) continue;
    seen.add(a.matched_player_id);
    const trouble = a.event_type === "injury/status" || a.event_type === "off-field/drama";
    rows.push({
      key: `alert:${a.alert_key}`,
      alertKey: a.alert_key,
      unread: !a.read,
      player: { id: a.matched_player_id, name: a.matched_player ?? "Player", position: a.matched_player_position, team: a.matched_player_team, tier: a.matched_player_tier, injuryStatus: null, note: null, stat: null },
      reason: a.title,
      button: starter ? (trouble ? "Swap" : "Lineup") : "Read",
      target: starter ? "matchup" : "link",
      link: a.link,
      tone: trouble ? "danger" : "accent",
    });
  }
  const rank = (r: TodayAlertRow) => (r.player && r.button !== "Read" ? 0 : 2) + (r.unread ? 0 : 1);
  const sorted = rows.map((r, i) => ({ r, i })).sort((a, b) => rank(a.r) - rank(b.r) || a.i - b.i).map((x) => x.r);
  return { rows: sorted.slice(0, max), total: sorted.length };
}

export interface TodayStandingPart {
  key: string;
  text: string;
  tone: Tone;
}

/** The slim standing line ("8th of 12 · 6-4 · Playoffs 72% · Rank #3"): the same tiles as todayTiles, on one line. */
export function todayStandingLine(tiles: ReadonlyArray<TodayTile>): TodayStandingPart[] {
  const parts: TodayStandingPart[] = [];
  for (const t of tiles) {
    if (t.key === "standing") parts.push({ key: t.key, text: [t.value, t.sub === "record" ? null : t.sub].filter(Boolean).join(" "), tone: "muted" });
    else if (t.key === "playoffs") parts.push({ key: t.key, text: `Playoffs ${t.value}`, tone: t.tone });
    else parts.push({ key: t.key, text: `Rank ${t.value}`, tone: "accent" });
  }
  return parts;
}
