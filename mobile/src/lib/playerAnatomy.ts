// Shared (web + mobile twin, byte-identical, import-free): the ONE player anatomy every player template renders
// (PlayerAccordionRow, CompactPlayerCard, trade assets, the peek sheet header). A template takes a `player` and
// draws the avatar itself, in the same slot (first, leading) at a size token for its density tier, so no module can
// show a name without a picture. Fantasy Sim passes mode "sim": letter grade / ADP / projection, never a numeric
// overall or the hidden trade value.

export type PlayerMode = "desk" | "sim";
export type AvatarTier = "dense" | "row" | "card" | "sheet";

/** Avatar diameter (px) per density tier. One table, so a row is the same size on every page. */
export const AVATAR_SIZE: Record<AvatarTier, number> = { dense: 28, row: 36, card: 44, sheet: 56 };

export function avatarSize(tier: AvatarTier): number {
  return AVATAR_SIZE[tier];
}

export interface PlayerRef {
  /** Player id (also the headshot id for real players). */
  id?: string | null;
  name: string;
  position?: string | null;
  team?: string | null;
  age?: number | null;
  /** Value tier id (ring colour). */
  tier?: string | null;
  /** Sleeper headshot id when it differs from `id`; generated sim players have none. */
  headshotId?: string | null;
}

/** "Ja'Marr Chase" -> "JC"; the fallback shown in the avatar ring when there is no photo or it fails to load. */
export function playerInitials(name: string | null | undefined): string {
  const words = (name ?? "")
    .replace(/[.,]/g, " ")
    .split(/\s+/)
    .filter((w) => w && !/^(jr|sr|ii|iii|iv|v)$/i.test(w));
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

export function playerHeadshotId(player: PlayerRef): string | null {
  return player.headshotId ?? player.id ?? null;
}

export type FactTone = "success" | "danger" | "warning" | "muted" | "accent";

export interface PlayerFact {
  key: string;
  label: string;
  value: string;
  tone?: FactTone;
}

export interface PlayerFactsInput {
  player: PlayerRef;
  mode: PlayerMode;
  /** Projected points (season or weekly, the caller's unit). */
  proj?: number | null;
  /** FantasyDesk trade value (0-100 style score). Ignored in sim mode. */
  value?: number | null;
  /** Signed value / rank trend. Ignored in sim mode. */
  trend?: number | null;
  /** Fantasy Sim letter grade ("A-"). Used in sim mode only. */
  grade?: string | null;
  adp?: number | null;
  /** Numeric overall. Never shown in sim mode. */
  ovr?: number | null;
  bye?: number | null;
  /** Short status ("Q", "OUT") shown in meta in the warning tone. */
  status?: string | null;
  /** Page-specific extra facts for the expanded tile (a sorted stat, a position rank). Desk only. */
  extraFacts?: PlayerFact[];
  /** Replaces the trailing key number (e.g. the column the list is sorted by, or a status header's gain figure). */
  trailingFact?: PlayerFact | null;
  /** Replaces the muted second line with ready-made text ("HOU · 12% rostered"). */
  metaText?: string | null;
}

export interface PlayerRowModel {
  /** Muted second line: TEAM · Age 25 · BYE 12 */
  meta: string[];
  /** The one trailing key number (or the sim letter grade). */
  trailing: PlayerFact | null;
  /** Expanded tile facts, never including anything the mode hides. */
  facts: PlayerFact[];
}

function num(value: number | null | undefined, digits = 1): string | null {
  return value == null || !Number.isFinite(value) ? null : value.toFixed(digits);
}

export function signedTrend(trend: number | null | undefined): PlayerFact | null {
  if (trend == null || !Number.isFinite(trend) || trend === 0) return null;
  return { key: "trend", label: "TREND", value: `${trend > 0 ? "▲" : "▼"} ${Math.abs(Math.round(trend))}`, tone: trend > 0 ? "success" : "danger" };
}

/** Everything a player row/card shows, per mode. The sim branch has no path to a numeric OVR or a trade value. */
export function playerRowModel(input: PlayerFactsInput): PlayerRowModel {
  const { player, mode } = input;
  const meta: string[] = [];
  if (player.team) meta.push(player.team);
  if (player.age != null) meta.push(`Age ${player.age}`);
  if (input.bye != null) meta.push(`BYE ${input.bye}`);
  const proj = num(input.proj);
  const adp = num(input.adp);
  if (input.metaText) meta.splice(0, meta.length, input.metaText);
  if (mode === "sim") {
    const facts: PlayerFact[] = [];
    if (input.grade) facts.push({ key: "grade", label: "GRADE", value: input.grade, tone: "accent" });
    if (adp) facts.push({ key: "adp", label: "ADP", value: adp });
    if (proj) facts.push({ key: "proj", label: "PROJ", value: proj });
    const trailing: PlayerFact | null = input.trailingFact ?? (input.grade
      ? { key: "grade", label: "GRADE", value: input.grade, tone: "accent" as const }
      : adp
        ? { key: "adp", label: "ADP", value: adp }
        : proj
          ? { key: "proj", label: "PROJ", value: proj }
          : null);
    return { meta, trailing, facts };
  }
  const facts: PlayerFact[] = [];
  if (proj) facts.push({ key: "proj", label: "PROJ", value: proj });
  const value = input.value != null && Number.isFinite(input.value) ? String(Math.round(input.value)) : null;
  if (value) facts.push({ key: "value", label: "VALUE", value, tone: "accent" });
  const trend = signedTrend(input.trend);
  if (trend) facts.push(trend);
  if (adp) facts.push({ key: "adp", label: "ADP", value: adp });
  if (input.ovr != null && Number.isFinite(input.ovr)) facts.push({ key: "ovr", label: "OVR", value: String(Math.round(input.ovr)) });
  for (const extra of input.extraFacts ?? []) facts.push(extra);
  const trailing: PlayerFact | null = input.trailingFact ?? (proj ? { key: "proj", label: "PROJ", value: proj } : value ? { key: "value", label: "VALUE", value, tone: "accent" as const } : null);
  return { meta, trailing, facts };
}

/** One open at a time: tapping the open row closes it, tapping another swaps. */
export function nextOpenId(current: string | null, tapped: string): string | null {
  return current === tapped ? null : tapped;
}

/**
 * Fairness meter for a trade. The marker sits on a band of +-METER_BAND (25%) of the trade's size, so a typical
 * trade is not a sliver in the middle: centre is even, the left end is "you lose by 25% or more", the right end is
 * "you win by 25% or more". Direction colours the fill (success when you win, danger when you lose, muted near even).
 * `sim` mode never shows a percentage: plain words and a coarse marker position (three steps each way) so the hidden
 * value cannot be read back off the marker.
 */
export interface FairnessMeter {
  /** 0..1 position of the marker on the clamped band; 0.5 is even. */
  position: number;
  /** Signed edge as a fraction of the trade size (positive = you win). Always 0 in sim mode (hidden). */
  edge: number;
  label: string;
  /** Screen-reader sentence describing the meter. */
  description: string;
  tone: FactTone;
}

/** Half-width of the meter band: the marker pins to an end at +-25%. */
export const METER_BAND = 0.25;

/**
 * Signed trade edge as a fraction of the larger side (-1..1; positive = you get more than you give).
 * `net` is the server's own net value (e.g. `trade_gain`) when it has one: pick values are often missing from the
 * asset sums, so the net wins and the trade size is taken as the larger of what you give and what you get.
 */
export function tradeEdge(giveValue: number, getValue: number, net?: number | null): number {
  const give = Math.max(0, Number.isFinite(giveValue) ? giveValue : 0);
  let get = Math.max(0, Number.isFinite(getValue) ? getValue : 0);
  if (net != null && Number.isFinite(net)) get = Math.max(0, give + net);
  const size = Math.max(give, get);
  if (size <= 0) return 0;
  return Math.max(-1, Math.min(1, (get - give) / size));
}

export function fairnessMeter(giveValue: number, getValue: number, mode: PlayerMode = "desk", net?: number | null): FairnessMeter {
  const edge = tradeEdge(giveValue, getValue, net);
  const abs = Math.abs(edge);
  const wins = edge > 0;
  if (mode === "sim") {
    const step = abs < 0.05 ? 0 : abs < 0.15 ? 1 : abs < 0.3 ? 2 : 3;
    const position = 0.5 + (wins ? 1 : -1) * step * (0.5 / 3);
    const label = step === 0 ? "About even" : wins ? (step === 1 ? "Slightly in your favor" : "In your favor") : step === 1 ? "Slightly in their favor" : "In their favor";
    return { position, edge: 0, label, description: `Trade fairness: ${label}`, tone: step === 0 ? "muted" : wins ? "success" : "danger" };
  }
  const position = 0.5 + Math.max(-1, Math.min(1, edge / METER_BAND)) * 0.5;
  const pct = Math.round(abs * 100);
  if (abs < 0.03) return { position, edge, label: "Even", description: "Trade fairness: even, within 3% either way", tone: "muted" };
  if (abs < 0.08) {
    const label = wins ? "Slight edge to you" : "Slight edge to them";
    return { position, edge, label, description: `Trade fairness: ${label.toLowerCase()}, about ${pct}%`, tone: wins ? "success" : "danger" };
  }
  const label = wins ? `You win by ~${pct}%` : `You lose by ~${pct}%`;
  return { position, edge, label, description: `Trade fairness: ${label.toLowerCase()} of the trade's value`, tone: wins ? "success" : "danger" };
}

/** Bar rows (waivers add row, standings row): each value as a 0..1 share of the largest, so the gap reads at a glance. */
export function barFractions(values: ReadonlyArray<number | null | undefined>): number[] {
  const max = Math.max(0, ...values.map((v) => (v != null && Number.isFinite(v) ? v : 0)));
  return values.map((v) => (max > 0 && v != null && Number.isFinite(v) ? Math.max(0, Math.min(1, v / max)) : 0));
}

export type SheetSnap = "peek" | "full";
/** Open heights of the player sheet in percent of the screen. */
export const SHEET_SNAP_PCT: Record<SheetSnap, number> = { peek: 56, full: 92 };

/** Drag the handle: up past 48px or a fast flick goes full, down past 48px from full goes back to peek. Down from peek is the dismiss gesture (not handled here). */
export function nextSheetSnap(current: SheetSnap, dragY: number, velocity = 0): SheetSnap {
  if (current === "peek" && (dragY < -48 || velocity < -0.6)) return "full";
  if (current === "full" && (dragY > 48 || velocity > 0.6)) return "peek";
  return current;
}

const PQV_ORDER = ["overview", "stats", "outlook", "history", "scouting", "profile"];
/** Pill order for the player sheet: Overview, Stats, Outlook, History, Scouting (then anything else). */
export function orderPlayerSheetTabs<T extends { key: string }>(tabs: readonly T[]): T[] {
  const rank = (k: string) => {
    const i = PQV_ORDER.indexOf(k);
    return i < 0 ? PQV_ORDER.length : i;
  };
  return [...tabs].sort((a, b) => rank(a.key) - rank(b.key));
}
