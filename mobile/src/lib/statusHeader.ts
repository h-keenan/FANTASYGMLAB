/**
 * The "Players-first status header" model (docs/ui-patterns.md, "StatusHeader"). One shape for the top of Today, My Team
 * and Fantasy Sim Home: a status ring, up to three mini stats, a short "Needs your attention" list of player rows (every
 * row carries a player avatar), then the ONE primary action. Pure and import-free; byte-identical twin of
 * mobile/src/lib/statusHeader.ts. Adapters below turn each page's real data into the shape, so the component never
 * knows which page it is on. The Fantasy Sim adapters never emit a numeric rating or Value: projection, ADP and
 * letter grades only.
 */

export type StatusTone = "success" | "danger" | "warning" | "accent" | "muted";

export const STATUS_STAT_LIMIT = 3;
export const STATUS_ATTENTION_LIMIT = 3;

export interface StatusRing {
  /** 0-100 fill; null draws an empty track (the centre text still shows). */
  pct: number | null;
  /** What sits in the middle: "71%", "#3", "5-1". Short. */
  center: string;
  /** Screen-reader name: "Win chance 71%". */
  label: string;
  tone: StatusTone;
}

export interface StatusMiniStat {
  key: string;
  label: string;
  value: string;
  tone?: StatusTone;
  /** Tapping the tile goes here (same destinations the InsightLink tiles used). */
  href?: string;
}

/** One player row in "Needs your attention". Rendered with the shared player row, so it always has an avatar. */
export interface StatusAttentionItem {
  key: string;
  /** Headshot id (Sleeper id; the sim's `headshot_id`). Null still draws the ringed avatar. */
  playerId: string | null;
  name: string;
  position: string | null;
  team: string | null;
  tier?: string | null;
  injuryStatus?: string | null;
  /** The muted second line: "HOU · 12% rostered", "Best available · ADP 5.1", "Out this week". */
  meta: string;
  /** The right-edge figure: "+4.1" with caption "GAIN", "11.4" with "PROJ". */
  stat?: { value: string; label: string; tone?: StatusTone } | null;
  /** Sim only: a letter grade ("A-"). Never a number. */
  grade?: string | null;
  /** One sentence shown when the row expands (why it needs attention). */
  detail?: string | null;
  href?: string;
}

export interface StatusPrimaryAction {
  label: string;
  href?: string;
  /** Page-handled actions (the sim switches tabs / runs a week) are identified by key. */
  actionKey?: string;
}

export interface StatusHeaderModel {
  kicker: string;
  headline: string;
  context: string | null;
  ring: StatusRing | null;
  stats: StatusMiniStat[];
  attention: StatusAttentionItem[];
  primary: StatusPrimaryAction | null;
}

/** Cap and clean a model: at most three stats and three rows, empty values dropped (never zero-filled). */
export function statusHeaderModel(model: StatusHeaderModel): StatusHeaderModel {
  return {
    ...model,
    stats: model.stats.filter((s) => s.value && s.value.trim()).slice(0, STATUS_STAT_LIMIT),
    attention: model.attention.filter((a) => a.name && a.name.trim()).slice(0, STATUS_ATTENTION_LIMIT),
  };
}

export function statusRingTone(pct: number | null | undefined): StatusTone {
  if (pct == null || Number.isNaN(pct)) return "accent";
  if (pct >= 55) return "success";
  if (pct <= 45) return "danger";
  return "accent";
}

/** A 0-100 fill from a win chance given as a whole percent; clamps to the ring's range. */
export function statusRing(pct: number | null | undefined, center: string, label: string, tone?: StatusTone): StatusRing {
  const clamped = pct == null || Number.isNaN(pct) ? null : Math.min(100, Math.max(0, Math.round(pct)));
  return { pct: clamped, center, label, tone: tone ?? statusRingTone(clamped) };
}

/** Rank to a 0-100 "how high up the league" fill (1st of 12 = 100, last = 0). Null when there is no honest rank. */
export function rankPercentile(rank: number | null | undefined, teams: number | null | undefined): number | null {
  if (rank == null || teams == null || teams < 2 || rank < 1) return null;
  return Math.round(((teams - Math.min(rank, teams)) / (teams - 1)) * 100);
}

/** "Alice Smith" -> "A. Smith" is the shared PlayerName's job; this only builds the screen-reader sentence. */
export function statusAttentionAria(item: StatusAttentionItem): string {
  const pos = item.position ? `, ${item.position}` : "";
  const stat = item.stat ? `, ${item.stat.label} ${item.stat.value}` : "";
  const grade = item.grade ? `, grade ${item.grade}` : "";
  return `${item.name}${pos}. ${item.meta}${stat}${grade}`;
}

const signed = (n: number): string => `${n >= 0 ? "+" : ""}${(Math.round(n * 10) / 10).toFixed(1)}`;

// ---------------------------------------------------------------------------------------------------------------------
// FantasyDesk adapters (Today and My Team)
// ---------------------------------------------------------------------------------------------------------------------

export interface StatusMovePlayerInput {
  player_id: string | null;
  name: string | null;
  position: string | null;
  team: string | null;
  tier: string | null;
  injury_label: string;
}

export interface StatusMoveInput {
  start: StatusMovePlayerInput;
  over: StatusMovePlayerInput | null;
  over_reason: "bye_week" | "ruled_out" | "empty_slot" | null;
  gain: number | null;
  locked: boolean;
}

const MOVE_REASON: Record<string, string> = { bye_week: "On bye this week", ruled_out: "Ruled out this week" };

/**
 * Lineup holes as player rows: the starter who cannot play (bye / out) with the swap that fixes it as the meta line and
 * the points the swap adds as the figure. Empty slots have no player to show, so they are counted in the headline, not here.
 */
export function lineupAttentionItems(moves: ReadonlyArray<StatusMoveInput> | null | undefined, limit: number = STATUS_ATTENTION_LIMIT, href?: string): StatusAttentionItem[] {
  const out: StatusAttentionItem[] = [];
  for (const move of moves ?? []) {
    if (move.locked || !move.over || !move.over.name || move.over_reason === null || move.over_reason === "empty_slot") continue;
    const reason = MOVE_REASON[move.over_reason] ?? "Cannot play this week";
    const swap = move.start.name ? `Start ${move.start.name} instead` : "Needs a replacement";
    out.push({
      key: `lineup-${move.over.player_id ?? move.over.name}`,
      playerId: move.over.player_id,
      name: move.over.name,
      position: move.over.position,
      team: move.over.team,
      tier: move.over.tier,
      injuryStatus: move.over.injury_label || null,
      meta: `${reason} · ${swap}`,
      stat: move.gain != null && move.gain > 0 ? { value: signed(move.gain), label: "GAIN", tone: "success" } : null,
      detail: `${reason}. ${swap}${move.gain != null && move.gain > 0 ? ` for about ${move.gain.toFixed(1)} more points` : ""}.`,
      href,
    });
    if (out.length >= limit) break;
  }
  return out;
}

export interface StatusBriefingInput {
  headline: string;
  reason: string;
  route_player_id: string;
  route_player_name: string;
  route_player_position: string;
  route_player_team: string;
  route_player_tier: string;
  route_player_score: number | null;
  route_player_injury_status: string;
}

/** Top-priority briefing items that name a single player (a waiver target, an injury alert) as player rows. */
export function briefingAttentionItems(items: ReadonlyArray<StatusBriefingInput> | null | undefined, hrefFor?: (item: StatusBriefingInput) => string | undefined): StatusAttentionItem[] {
  const out: StatusAttentionItem[] = [];
  for (const item of items ?? []) {
    if (!item.route_player_id || !item.route_player_name) continue;
    out.push({
      key: `item-${item.route_player_id}-${out.length}`,
      playerId: item.route_player_id,
      name: item.route_player_name,
      position: item.route_player_position || null,
      team: item.route_player_team || null,
      tier: item.route_player_tier || null,
      injuryStatus: item.route_player_injury_status || null,
      meta: item.headline,
      stat: null,
      detail: item.reason || null,
      href: hrefFor?.(item),
    });
  }
  return out;
}

export interface StatusRosterPlayerInput {
  player_id: string;
  name: string | null;
  position: string | null;
  team: string | null;
  tier: string | null;
  injury_label: string;
  injury_status: string | null;
  ruled_out: boolean;
  start_ineligible_reason?: string | null;
  slot: string | null;
  lineup_points?: number | null;
}

/** My Team: starters who cannot play this week (out, bye, IR) or carry an injury tag, worst first. */
export function rosterAttentionItems(starters: ReadonlyArray<StatusRosterPlayerInput> | null | undefined, limit: number = STATUS_ATTENTION_LIMIT, href?: string): StatusAttentionItem[] {
  const flagged = (starters ?? [])
    .filter((p) => p.name && (p.ruled_out || p.start_ineligible_reason || (p.injury_label && p.injury_label.trim())))
    .sort((a, b) => Number(Boolean(b.ruled_out || b.start_ineligible_reason)) - Number(Boolean(a.ruled_out || a.start_ineligible_reason)));
  return flagged.slice(0, limit).map((p) => {
    const reason = p.start_ineligible_reason || (p.ruled_out ? "Out" : p.injury_label);
    return {
      key: `roster-${p.player_id}`,
      playerId: p.player_id,
      name: p.name as string,
      position: p.position,
      team: p.team,
      tier: p.tier,
      injuryStatus: p.injury_status,
      meta: [p.slot ? `Starting ${p.slot}` : null, reason].filter(Boolean).join(" · "),
      stat: p.lineup_points != null ? { value: (Math.round(p.lineup_points * 10) / 10).toFixed(1), label: "PROJ" } : null,
      detail: `${p.name} ${p.ruled_out || p.start_ineligible_reason ? "cannot start" : "is flagged"} this week: ${reason}.`,
      href,
    };
  });
}

// ---------------------------------------------------------------------------------------------------------------------
// Fantasy Sim adapters (Home). Projection / ADP / letter grade only, never the numeric rating.
// ---------------------------------------------------------------------------------------------------------------------

export interface StatusSimPlayerInput {
  id: string;
  headshot_id?: string | null;
  name: string;
  pos: string;
  team: string | null;
  adp?: number | null;
  projection: number;
  status?: "healthy" | "out" | "bye";
}

const simProj = (p: StatusSimPlayerInput): { value: string; label: string } => ({ value: (Math.round(p.projection * 10) / 10).toFixed(1), label: "PROJ" });

function simItem(p: StatusSimPlayerInput, meta: string, extra: Partial<StatusAttentionItem> = {}): StatusAttentionItem {
  return { key: `sim-${p.id}`, playerId: p.headshot_id ?? null, name: p.name, position: p.pos, team: p.team, meta, stat: simProj(p), ...extra };
}

export interface StatusSimHomeInput {
  injuries?: ReadonlyArray<{ player: StatusSimPlayerInput; starting: boolean; out_weeks: number; note: string }> | null;
  bye_alerts?: ReadonlyArray<{ player: StatusSimPlayerInput; covered: boolean; week: number; message: string }> | null;
  waiver_suggestions?: ReadonlyArray<{ player: StatusSimPlayerInput; gain_now: number; gain_ros: number; for_slot: string | null }> | null;
}

/** Starters who are out first, then uncovered byes, then the best waiver target: the order a manager fixes them in. */
export function simHomeAttentionItems(home: StatusSimHomeInput, limit: number = STATUS_ATTENTION_LIMIT): StatusAttentionItem[] {
  const out: StatusAttentionItem[] = [];
  const seen = new Set<string>();
  const push = (item: StatusAttentionItem) => {
    if (seen.has(item.key) || out.length >= limit) return;
    seen.add(item.key);
    out.push(item);
  };
  for (const inj of home.injuries ?? []) {
    if (!inj.starting) continue;
    push(simItem(inj.player, `Starter out ${inj.out_weeks} wk`, { injuryStatus: "Out", stat: null, detail: inj.note || null }));
  }
  for (const bye of home.bye_alerts ?? []) {
    if (bye.covered) continue;
    push(simItem(bye.player, `Bye wk ${bye.week} · needs cover`, { stat: null, detail: bye.message || null }));
  }
  const top = (home.waiver_suggestions ?? [])[0];
  if (top) {
    const gain = Math.max(top.gain_now, top.gain_ros);
    push(simItem(top.player, `Waiver target${top.for_slot ? ` for ${top.for_slot}` : ""}${top.player.adp != null ? ` · ADP ${top.player.adp.toFixed(1)}` : ""}`, { stat: gain > 0 ? { value: signed(gain), label: "GAIN", tone: "success" } : simProj(top.player) }));
  }
  return out;
}

// ---------------------------------------------------------------------------------------------------------------------
// Page models. Structural inputs only (no imports), so the same builders run on web and in the app.
// ---------------------------------------------------------------------------------------------------------------------

export interface TodayStatusInput {
  /** This week's modeled matchup (lib/teamStatus buildTeamStatusMatchup), or null. */
  matchup: { week: number | null; opponentName: string; winPercent: number | null; live: { mine: number; opponent: number } | null } | null;
  /** The Hero model (teamStatusHeroModel): the one number that matters this week. */
  hero: { label: string; value: string; context: string | null } | null;
  lineup: { tone: "positive" | "risk" | "warning" | "neutral"; headline: string } | null;
  standing: { place: string | null; record: string | null; playoffOdds: string | null; tone: "positive" | "risk" | "warning" | "neutral" } | null;
  attention: StatusAttentionItem[];
  tradeCount: number;
  hrefs: { matchup: string; rankings: string; trades: string };
}

const toneOf = (t: "positive" | "risk" | "warning" | "neutral" | undefined): StatusTone | undefined => (t === "positive" ? "success" : t === "risk" ? "danger" : t === "warning" ? "warning" : undefined);

/** Today: ring = win chance; headline = the lineup hole when there is one, else the hero number; one cyan action. */
export function buildTodayStatusHeader(input: TodayStatusInput): StatusHeaderModel | null {
  const { matchup, hero, lineup, standing, attention, tradeCount, hrefs } = input;
  const wp = matchup?.winPercent ?? null;
  const ring = wp != null ? statusRing(wp, `${wp}%`, `Win chance ${wp}%`) : null;
  const lineupRisk = lineup?.tone === "risk";
  const fallback = attention.length === 1 ? "1 item needs you" : `${attention.length} items need you`;
  const headline = lineupRisk ? lineup!.headline : hero ? `${hero.label}: ${hero.value}` : (lineup?.headline ?? (attention.length > 0 ? fallback : ""));
  if (!headline) return null;
  const stats: StatusMiniStat[] = [];
  const place = standing?.place ?? standing?.record ?? null;
  if (place) stats.push({ key: "standing", label: standing?.place ? "Standing" : "Record", value: place, href: hrefs.rankings });
  if (standing?.playoffOdds) stats.push({ key: "odds", label: "Playoffs", value: standing.playoffOdds, tone: toneOf(standing.tone), href: hrefs.rankings });
  if (tradeCount > 0) stats.push({ key: "trades", label: "Trades", value: `${tradeCount} ${tradeCount === 1 ? "idea" : "ideas"}`, href: hrefs.trades });
  return statusHeaderModel({
    kicker: matchup?.week != null ? `TODAY · WEEK ${matchup.week}` : "TODAY",
    headline,
    context: hero?.context ?? null,
    ring,
    stats,
    attention,
    primary: lineupRisk ? { label: "Fix lineup", href: hrefs.matchup } : tradeCount > 0 && attention.length === 0 ? { label: "Review trade ideas", href: hrefs.trades } : null,
  });
}

export interface TeamStatusInput {
  teamValue: string;
  /** 0-100 league percentile of team value, or null. */
  valuePercentile: number | null;
  leagueSize: number | null;
  context: string | null;
  record: string | null;
  openSlots: number;
  flaggedStarters: number;
  injuredStarters: number;
  attention: StatusAttentionItem[];
  hrefs: { lineup: string };
}

/** My Team: ring = value percentile; headline = Team Value (or the roster hole); stats = record / holes / injured. */
export function buildTeamStatusHeader(input: TeamStatusInput): StatusHeaderModel {
  const holes = input.openSlots + input.flaggedStarters;
  const pct = input.valuePercentile;
  const ring = pct != null ? statusRing(pct, `${Math.round(pct)}`, `Team value percentile ${Math.round(pct)}${input.leagueSize ? ` of ${input.leagueSize} teams` : ""}`, "accent") : null;
  const stats: StatusMiniStat[] = [];
  if (input.record) stats.push({ key: "record", label: "Record", value: input.record });
  stats.push({ key: "holes", label: "Holes", value: String(holes), tone: holes > 0 ? "danger" : "success", href: holes > 0 ? input.hrefs.lineup : undefined });
  stats.push({ key: "injured", label: "Injured", value: String(input.injuredStarters), tone: input.injuredStarters > 0 ? "warning" : "success" });
  return statusHeaderModel({
    kicker: "TEAM",
    headline: holes > 0 ? `${holes} ${holes === 1 ? "hole" : "holes"} in your lineup` : `Team Value ${input.teamValue}`,
    context: holes > 0 ? [`Team Value ${input.teamValue}`, input.context].filter(Boolean).join(" · ") : input.context,
    ring,
    stats,
    attention: input.attention,
    primary: holes > 0 ? { label: "Fix lineup", href: input.hrefs.lineup } : null,
  });
}

export interface SimStatusInput {
  week: number | null;
  seasonLabel: string | null;
  record: string | null;
  /** Whole-game rank, e.g. 2. */
  rank: number | null;
  teams: number | null;
  inPlayoffs: boolean | null;
  opponentName: string | null;
  /** 0-1 chance of winning this week. */
  winProb: number | null;
  bye: boolean;
  injuredCount: number;
  offers: number;
  waiverTargets: number;
  attention: StatusAttentionItem[];
  /** The first unfinished checklist item, as the one action ("Set lineup" -> team tab). */
  next: { label: string; actionKey: string } | null;
}

/** Fantasy Sim Home: ring = win chance; the same shape as Today. No numeric rating anywhere. */
export function buildSimStatusHeader(input: SimStatusInput): StatusHeaderModel {
  const pct = input.winProb != null ? Math.min(99, Math.max(1, Math.round(input.winProb * 100))) : null;
  const ring = input.bye ? null : pct != null ? statusRing(pct, `${pct}%`, `Win chance ${pct}%`) : null;
  const kicker = [input.week != null ? `WEEK ${input.week}` : null, input.seasonLabel ? input.seasonLabel.toUpperCase() : null].filter(Boolean).join(" · ") || "HOME";
  const stats: StatusMiniStat[] = [];
  if (input.rank != null) stats.push({ key: "standing", label: "Standing", value: `#${input.rank}${input.teams ? ` of ${input.teams}` : ""}`, tone: input.inPlayoffs ? "success" : undefined });
  stats.push({ key: "injuries", label: "Injuries", value: String(input.injuredCount), tone: input.injuredCount > 0 ? "danger" : "success" });
  if (input.offers > 0) stats.push({ key: "offers", label: "Offers", value: String(input.offers), tone: "accent" });
  else if (input.waiverTargets > 0) stats.push({ key: "waivers", label: "Targets", value: String(input.waiverTargets), tone: "accent" });
  return statusHeaderModel({
    kicker,
    headline: input.record ? `You are ${input.record}` : "Your week",
    context: input.bye ? "Bye week: work the wire and your trades" : input.opponentName ? `Next: vs ${input.opponentName}${pct != null ? `, ${pct}% to win` : ""}` : null,
    ring,
    stats,
    attention: input.attention,
    primary: input.next ? { label: input.next.label, actionKey: input.next.actionKey } : null,
  });
}

/**
 * Today: the "Needs attention" entries and the lineup holes, split into the player rows the status header shows and the
 * entries that stay in the plain "Needs attention" card (a deadline, an item with no single player). Nothing is dropped:
 * an entry leaves the card only when a player row now says the same thing.
 */
export function splitTodayAttention<E extends { source: string; item?: StatusBriefingInput }>(
  entries: ReadonlyArray<E>,
  moves: ReadonlyArray<StatusMoveInput> | null | undefined,
  hrefFor: (entry: E) => string | undefined,
  lineupHref?: string,
  limit: number = STATUS_ATTENTION_LIMIT,
): { rows: StatusAttentionItem[]; remaining: E[] } {
  const lineupRows = lineupAttentionItems(moves, limit, lineupHref);
  const rows: StatusAttentionItem[] = [...lineupRows];
  const absorbed = new Set<E>();
  if (lineupRows.length > 0) {
    for (const entry of entries) if (entry.source === "lineup") absorbed.add(entry);
  }
  for (const entry of entries) {
    if (rows.length >= limit) break;
    if (!entry.item || entry.source !== "item") continue;
    const [row] = briefingAttentionItems([entry.item], () => hrefFor(entry));
    if (!row || rows.some((r) => r.playerId && r.playerId === row.playerId)) continue;
    rows.push(row);
    absorbed.add(entry);
  }
  return { rows, remaining: entries.filter((e) => !absorbed.has(e)) };
}
