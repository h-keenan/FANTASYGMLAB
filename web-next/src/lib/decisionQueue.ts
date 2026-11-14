/**
 * The Today "Decision Queue" (docs/ui-patterns.md, "Decision Queue"; UI pass 3 sheet 1, topic 1 V1): ONE next action and
 * at most three prioritised decisions, with the rest behind "See all (N)". Pure and import-free; byte-identical twin of
 * mobile/src/lib/decisionQueue.ts. Web and the app feed it the same real Dashboard + Matchup data and render the result
 * with the same shared templates.
 *
 * Nothing is invented: every decision is read from a field the Dashboard already has (matchup suggested moves, the
 * "This week" rows, the briefing items, the trade window). The queue only DEDUPES and ORDERS:
 *   - the lineup issue is one decision no matter how many sources mention it (moves, the lineup row, a needs-attention
 *     entry, an injury alert about the same player);
 *   - all waiver sources (the waiver row and waiver briefing items) are one decision;
 *   - the same alert title never appears twice;
 *   - plain trade ideas stay in the Trade ideas module below; a trade idea only enters the queue as part of the
 *     "Trade deadline" decision (the expiry is what makes it urgent).
 *
 * Order: urgency desc, then impact desc, then a fixed kind order, then key, so the same input always gives the same
 * queue. Free vs Pro is unchanged: the server already caps the items a Free account sees, and the queue only surfaces
 * the "N more on Pro" line when `hiddenCount` says there are some.
 */

// SHARED BEGIN
export const DECISION_VISIBLE_LIMIT = 3;

export type DecisionKind = "live_draft" | "lineup" | "deadline" | "injury" | "waiver" | "draft" | "item";
export type DecisionTone = "danger" | "warning" | "accent" | "success";
export type DecisionTarget = "matchup" | "waivers" | "trade_hub" | "gm_plan" | "draft_center" | "live_draft" | "item";

/** Base urgency per kind (0-100). Deadline and waiver urgency is adjusted by the calendar below. */
export const DECISION_URGENCY = {
  live_draft: 100,
  lineup: 90,
  deadline_this_week: 88,
  deadline_next_week: 78,
  injury: 76,
  waiver_day: 74,
  waiver: 62,
  draft: 58,
  item: 52,
} as const;

const KIND_ORDER: Record<DecisionKind, number> = { live_draft: 0, lineup: 1, deadline: 2, injury: 3, waiver: 4, draft: 5, item: 6 };

const KIND_LABEL: Record<DecisionKind, string> = {
  live_draft: "DRAFT",
  lineup: "LINEUP",
  deadline: "DEADLINE",
  injury: "INJURY",
  waiver: "WAIVERS",
  draft: "DRAFT",
  item: "TOP PRIORITY",
};

export interface DecisionMovePlayer {
  player_id: string | null;
  name: string | null;
  position: string | null;
  team: string | null;
  tier: string | null;
  injury_label: string;
}

export interface DecisionMove {
  start: DecisionMovePlayer;
  over: DecisionMovePlayer | null;
  over_reason: "bye_week" | "ruled_out" | "empty_slot" | null;
  gain: number | null;
  locked: boolean;
}

export interface DecisionWeekRow {
  key: string;
  status: string;
  tone: string;
  headline: string;
  why: string;
  cta_label: string | null;
  route: string | null;
  player_id: string;
}

export interface DecisionItem {
  category: string;
  headline: string;
  reason: string;
  destination: string;
  route_player_id: string;
  route_player_name: string;
  route_player_position: string;
  route_player_team: string;
  route_player_tier: string;
  route_player_score: number | null;
  route_player_injury_status: string;
  mentioned_players?: ReadonlyArray<{ player_id: string }> | null;
  presentation?: { trade_package?: unknown } | null;
}

export interface DecisionTradeWindow {
  trade_deadline_week: number | null;
  current_week: number | null;
  trade_deadline_passed: boolean;
}

export interface DecisionInput<T extends DecisionItem = DecisionItem> {
  /** Injected so tests (and the weekday rule) are deterministic. */
  now: Date;
  /** Matchup suggested moves, once the matchup read has settled (null while unknown). */
  moves: ReadonlyArray<DecisionMove> | null | undefined;
  /** Matchup open slots (count). */
  openSlots?: number;
  thisWeek: {
    week: number | null;
    rows: ReadonlyArray<DecisionWeekRow>;
    next_action: { headline: string; why: string; cta_label: string; route: string } | null;
  } | null | undefined;
  items: ReadonlyArray<T>;
  tradeWindow: DecisionTradeWindow | null | undefined;
  /** Trade ideas the Dashboard found (a real give/get package each). */
  tradeIdeaCount?: number;
  entitlement?: { isPremium: boolean; hiddenCount: number } | null;
  /** This week's opponent, for the empty state's "next game" line. */
  nextGame?: { week: number | null; opponentName: string } | null;
}

export interface DecisionPlayer {
  id: string | null;
  name: string;
  position: string | null;
  team: string | null;
  tier: string | null;
  injuryStatus: string | null;
  /** The muted second line under the name ("On bye this week", "FAAB $6"). */
  note: string | null;
  /** The one figure at the right edge ("+4.1" with caption "GAIN"). */
  stat: { value: string; label: string } | null;
}

export interface DecisionAction {
  label: string;
  target: DecisionTarget;
  /** Waivers / Trade Hub open on this player when set. */
  playerId?: string;
}

export interface Decision<T extends DecisionItem = DecisionItem> {
  key: string;
  kind: DecisionKind;
  /** 1-based position in the ordered queue. */
  rank: number;
  urgency: number;
  impact: number;
  tone: DecisionTone;
  /** Small caps kicker: LINEUP, WAIVERS, DEADLINE. */
  label: string;
  title: string;
  /** One line shown collapsed under the title. */
  summary: string;
  /** The reasons, shown when the row expands. */
  why: string | null;
  players: DecisionPlayer[];
  primary: DecisionAction;
  /** The briefing item behind it, so the page can render its full card when expanded. */
  item: T | null;
  /** Extra expanded-only facts ("2 trade ideas", "Deadline Wk 12"). */
  facts: string[];
}

export interface DecisionQueue<T extends DecisionItem = DecisionItem> {
  /** Every decision, ordered. */
  all: Decision<T>[];
  /** At most DECISION_VISIBLE_LIMIT. */
  visible: Decision<T>[];
  /** The rest, behind "See all (N)". */
  rest: Decision<T>[];
  /** "See all (N)" count: every decision. 0 when nothing needs the user. */
  total: number;
  /** The one next action the hero leads with. Null when the queue is empty. */
  next: Decision<T> | null;
  /** Free account with moves hidden behind Pro: the "N more on Pro" line. */
  proUpsell: { hidden: number } | null;
  /** Set only when `all` is empty. */
  empty: { title: string; detail: string | null } | null;
}

const EMPTY_TITLE = "Nothing needs you this week";

/** Case/punctuation/"(+N more)"-insensitive title, so the same alert never shows twice. */
function normTitle(title: string | null | undefined): string {
  return (title ?? "")
    .toLowerCase()
    .replace(/\(\+\d+ more\)/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

const round1 = (n: number): number => Math.round(n * 10) / 10;
const plural = (n: number, word: string): string => `${n} ${word}${n === 1 ? "" : "s"}`;

/** Tuesday and Wednesday: the week's games are over and waivers clear (same rule as lib/todayPlan.ts). */
export function isWaiverDay(now: Date): boolean {
  const day = now.getDay();
  return day === 2 || day === 3;
}

/** "Next up: Week 7 vs Mock Mavericks" (or the pieces that are known); null when nothing is known. Never guessed. */
export function nextGameLine(nextGame: { week: number | null; opponentName: string } | null | undefined): string | null {
  if (!nextGame) return null;
  const opp = nextGame.opponentName?.trim();
  if (nextGame.week != null && opp) return `Next up: Week ${nextGame.week} vs ${opp}`;
  if (opp) return `Next up: vs ${opp}`;
  if (nextGame.week != null) return `Next up: Week ${nextGame.week}`;
  return null;
}

function mapPlayer(p: DecisionMovePlayer, note: string | null, stat: DecisionPlayer["stat"]): DecisionPlayer {
  return {
    id: p.player_id,
    name: p.name ?? "",
    position: p.position,
    team: p.team,
    tier: p.tier,
    injuryStatus: p.injury_label || null,
    note,
    stat,
  };
}

function itemPlayer(item: DecisionItem, note: string | null): DecisionPlayer | null {
  if (!item.route_player_id || !item.route_player_name) return null;
  return {
    id: item.route_player_id,
    name: item.route_player_name,
    position: item.route_player_position || null,
    team: item.route_player_team || null,
    tier: item.route_player_tier || null,
    injuryStatus: item.route_player_injury_status || null,
    note,
    stat: null,
  };
}

function isTrade(item: DecisionItem): boolean {
  return Boolean(item.presentation && item.presentation.trade_package);
}

function lineupDecision(input: DecisionInput): Decision | null {
  const moves = (input.moves ?? []).filter((m) => !m.locked && m.over_reason !== null);
  const holes = moves.filter((m) => m.over_reason !== "empty_slot" && m.over && m.over.name);
  const empty = moves.filter((m) => m.over_reason === "empty_slot").length + Math.max(0, input.openSlots ?? 0);
  const weekRow = (input.thisWeek?.rows ?? []).find((r) => r.key === "lineup" && r.tone === "risk") ?? null;
  if (holes.length === 0 && empty === 0 && !weekRow) return null;

  const players: DecisionPlayer[] = holes.slice(0, DECISION_VISIBLE_LIMIT).map((m) => {
    const why = m.over_reason === "bye_week" ? "On bye this week" : "Ruled out this week";
    const swap = m.start.name ? `Start ${m.start.name} instead` : "Needs a replacement";
    const gain = m.gain != null && m.gain > 0 ? { value: `+${round1(m.gain).toFixed(1)}`, label: "GAIN" } : null;
    return mapPlayer(m.over as DecisionMovePlayer, `${why} · ${swap}`, gain);
  });
  const impact = Math.min(99, round1(holes.reduce((sum, m) => sum + Math.max(0, m.gain ?? 0), 0)));
  const parts: string[] = [];
  if (holes.length > 0) parts.push(`${plural(holes.length, "starter")} can't play (bye or out)`);
  if (empty > 0) parts.push(plural(empty, "open slot"));
  const title = parts.length > 0 ? parts.join(", ") : (weekRow?.headline ?? "Fix your lineup");
  const best = [...holes].sort((x, y) => (y.gain ?? 0) - (x.gain ?? 0))[0];
  const swap = best && best.start.name ? `Best swap: start ${best.start.name}${best.over?.name ? ` over ${best.over.name}` : ""}${best.gain && best.gain > 0 ? ` (+${round1(best.gain)} pts)` : ""}` : null;
  const summary = swap ?? weekRow?.why ?? (parts.length > 0 ? "Fix it before lineups lock" : "A starter cannot play this week");
  const facts = holes.length > 0 && impact > 0 ? [`Swaps add about ${impact.toFixed(1)} projected points`] : [];
  return {
    key: "lineup",
    kind: "lineup",
    rank: 0,
    urgency: DECISION_URGENCY.lineup,
    impact,
    tone: "danger",
    label: KIND_LABEL.lineup,
    title,
    summary,
    why: weekRow?.why ?? (holes.length > 0 ? "A starter who is out or on bye scores nothing. The swap below is the best healthy replacement on your roster." : null),
    players,
    primary: { label: "Fix lineup", target: "matchup" },
    item: null,
    facts,
  };
}

function deadlineDecision(input: DecisionInput): Decision | null {
  const w = input.tradeWindow;
  if (!w || w.trade_deadline_passed || w.trade_deadline_week == null) return null;
  const current = w.current_week;
  if (current == null || current > w.trade_deadline_week) return null;
  const left = w.trade_deadline_week - current;
  if (left > 1) return null;
  const ideas = Math.max(0, input.tradeIdeaCount ?? 0);
  const when = left === 0 ? `This week (Wk ${w.trade_deadline_week})` : `1 wk left (Wk ${w.trade_deadline_week})`;
  return {
    key: "deadline",
    kind: "deadline",
    rank: 0,
    urgency: left === 0 ? DECISION_URGENCY.deadline_this_week : DECISION_URGENCY.deadline_next_week,
    impact: ideas,
    tone: "warning",
    label: KIND_LABEL.deadline,
    title: `Trade deadline: ${when}`,
    summary: ideas > 0 ? `${plural(ideas, "trade idea")} ready to review` : "Trades lock after the deadline",
    why: "Trades lock after the deadline. Review your plan before then.",
    players: [],
    primary: ideas > 0 ? { label: "Review ideas", target: "trade_hub" } : { label: "Open GM Plan", target: "gm_plan" },
    item: null,
    facts: ideas > 0 ? [plural(ideas, "trade idea")] : [],
  };
}

function waiverDecision(input: DecisionInput, taken: Set<string>): Decision | null {
  const waiverItems = input.items.filter((i) => i.category === "top_priority" && i.destination === "waivers" && !isTrade(i));
  const row = (input.thisWeek?.rows ?? []).find((r) => r.key === "waiver") ?? null;
  if (waiverItems.length === 0 && !row) return null;
  const players: DecisionPlayer[] = [];
  const seen = new Set<string>();
  const add = (p: DecisionPlayer | null) => {
    if (!p || (p.id && seen.has(p.id))) return;
    if (p.id) seen.add(p.id);
    players.push(p);
  };
  for (const item of waiverItems) add(itemPlayer(item, item.headline));
  const top = waiverItems[0] ?? null;
  const rowPlayer = row?.player_id ? row.player_id : "";
  if (row && rowPlayer && !seen.has(rowPlayer)) {
    // The row's player was not in a waiver card: it is still the same single waiver decision.
    players.push({ id: rowPlayer, name: "", position: null, team: null, tier: null, injuryStatus: null, note: row.headline, stat: null });
  }
  const named = players.filter((p) => p.name);
  for (const item of waiverItems) taken.add(normTitle(item.headline));
  const day = isWaiverDay(input.now);
  const impact = Math.max(0, ...waiverItems.map((i) => i.route_player_score ?? 0));
  const title = top ? top.headline : (row?.headline ?? "Waiver opportunity");
  const first = named[0] ?? null;
  return {
    key: "waiver",
    kind: "waiver",
    rank: 0,
    urgency: day ? DECISION_URGENCY.waiver_day : DECISION_URGENCY.waiver,
    impact,
    tone: "accent",
    label: KIND_LABEL.waiver,
    title,
    summary: day ? "Waivers clear today and tomorrow" : (row?.why ?? top?.reason ?? "A waiver add fits your roster"),
    why: [top?.reason, row && row.why !== top?.reason ? row.why : null].filter(Boolean).join(" ") || null,
    players: named,
    primary: { label: named.length > 1 ? "Review adds" : "Claim", target: "waivers", playerId: first?.id ?? (rowPlayer || undefined) },
    item: top,
    facts: named.length > 1 ? [`${named.length} recommended adds`] : [],
  };
}

function nextActionDecision(input: DecisionInput): Decision | null {
  const next = input.thisWeek?.next_action;
  if (!next) return null;
  const live = next.route === "live_draft";
  if (!live && next.route !== "draft_center") return null; // trade_hub / connect_league are not decisions here
  return {
    key: live ? "live_draft" : "draft",
    kind: live ? "live_draft" : "draft",
    rank: 0,
    urgency: live ? DECISION_URGENCY.live_draft : DECISION_URGENCY.draft,
    impact: 0,
    tone: live ? "danger" : "accent",
    label: KIND_LABEL[live ? "live_draft" : "draft"],
    title: next.headline,
    summary: next.why,
    why: next.why,
    players: [],
    primary: { label: next.cta_label || (live ? "Join draft" : "Open draft"), target: live ? "live_draft" : "draft_center" },
    item: null,
    facts: [],
  };
}

function itemTarget(destination: string): DecisionTarget {
  if (destination === "waivers") return "waivers";
  if (destination === "trade_hub") return "trade_hub";
  if (destination === "draft_center") return "draft_center";
  return "item";
}

function itemVerb(destination: string): string {
  if (destination === "waivers") return "Claim";
  if (destination === "trade_hub") return "Review";
  if (destination === "draft_center") return "Open draft";
  return "Open";
}

/** Build the ordered, deduped, capped queue. */
export function buildDecisionQueue<T extends DecisionItem>(input: DecisionInput<T>): DecisionQueue<T> {
  const out: Decision<T>[] = [];
  const takenTitles = new Set<string>();

  const lineup = lineupDecision(input);
  if (lineup) out.push(lineup as Decision<T>);
  const lineupIds = new Set((lineup?.players ?? []).map((p) => p.id).filter(Boolean) as string[]);

  const deadline = deadlineDecision(input);
  if (deadline) out.push(deadline as Decision<T>);

  const waiver = waiverDecision(input, takenTitles);
  if (waiver) out.push(waiver as Decision<T>);

  const draft = nextActionDecision(input);
  if (draft) out.push(draft as Decision<T>);

  const waiverPlayerIds = new Set((waiver?.players ?? []).map((p) => p.id).filter(Boolean) as string[]);
  for (const item of input.items) {
    if (item.category !== "top_priority") continue;
    if (isTrade(item)) continue; // trade ideas live in the Trade ideas module (and the deadline decision)
    if (item.destination === "waivers") continue; // merged into the one waiver decision
    const title = normTitle(item.headline);
    if (!title || takenTitles.has(title)) continue;
    const mentioned = (item.mentioned_players ?? []).map((p) => p.player_id).filter(Boolean);
    const coveredByLineup =
      (item.route_player_id && lineupIds.has(item.route_player_id)) || (mentioned.length > 0 && mentioned.every((id) => lineupIds.has(id)));
    if (coveredByLineup) continue; // the lineup decision already says it (the lineup issue appears once)
    if (item.route_player_id && waiverPlayerIds.has(item.route_player_id)) continue;
    takenTitles.add(title);
    const injured = Boolean(item.route_player_injury_status && item.route_player_injury_status.trim());
    const kind: DecisionKind = injured ? "injury" : "item";
    const player = itemPlayer(item, injured ? item.route_player_injury_status : null);
    out.push({
      key: `item-${out.length}-${title.replace(/ /g, "-").slice(0, 40)}`,
      kind,
      rank: 0,
      urgency: injured ? DECISION_URGENCY.injury : DECISION_URGENCY.item,
      impact: item.route_player_score ?? 0,
      tone: injured ? "danger" : "accent",
      label: KIND_LABEL[kind],
      title: item.headline,
      summary: item.reason,
      why: item.reason || null,
      players: player ? [player] : [],
      primary: { label: itemVerb(item.destination), target: itemTarget(item.destination), playerId: item.route_player_id || undefined },
      item,
      facts: [],
    });
  }

  out.sort((a, b) => b.urgency - a.urgency || b.impact - a.impact || KIND_ORDER[a.kind] - KIND_ORDER[b.kind] || (a.key < b.key ? -1 : a.key > b.key ? 1 : 0));
  out.forEach((d, i) => {
    d.rank = i + 1;
  });

  const ent = input.entitlement;
  const proUpsell = ent && !ent.isPremium && ent.hiddenCount > 0 ? { hidden: ent.hiddenCount } : null;
  return {
    all: out,
    visible: out.slice(0, DECISION_VISIBLE_LIMIT),
    rest: out.slice(DECISION_VISIBLE_LIMIT),
    total: out.length,
    next: out[0] ?? null,
    proUpsell,
    empty: out.length === 0 ? { title: EMPTY_TITLE, detail: nextGameLine(input.nextGame) } : null,
  };
}

export interface DecisionSummaryPart {
  key: string;
  text: string;
  tone?: DecisionTone | "muted";
  strong?: boolean;
}

/** The collapsed summary line: the title (bold, toned) then the one-line reason ("1 starter on bye or out"). */
export function decisionSummaryParts(d: Decision): DecisionSummaryPart[] {
  const parts: DecisionSummaryPart[] = [{ key: "title", text: d.title, tone: d.tone, strong: true }];
  if (d.summary && d.summary !== d.title) parts.push({ key: "summary", text: d.summary, tone: "muted" });
  return parts;
}

/** "See all (N)" label; the toggle reads "Show top 3" once opened. Null when nothing is hidden. */
export function seeAllLabel(queue: { total: number; rest: unknown[] }, open: boolean): string | null {
  if (queue.rest.length === 0) return null;
  return open ? `Show top ${DECISION_VISIBLE_LIMIT}` : `See all (${queue.total})`;
}
// SHARED END
