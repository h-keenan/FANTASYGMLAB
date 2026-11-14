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

/** Fairness meter for a trade (recommended V3): the share of the combined value that comes to you. */
export interface FairnessMeter {
  /** 0..1 position of the marker; 0.5 is even. */
  position: number;
  label: string;
  tone: FactTone;
}

export function fairnessMeter(giveValue: number, getValue: number, mode: PlayerMode = "desk"): FairnessMeter {
  const total = Math.max(0, giveValue) + Math.max(0, getValue);
  const position = total > 0 ? Math.min(1, Math.max(0, getValue / total)) : 0.5;
  const edge = position - 0.5;
  if (Math.abs(edge) < 0.04) return { position, label: mode === "sim" ? "About even" : "Fair", tone: "muted" };
  if (edge > 0) return { position, label: mode === "sim" ? "A better deal for you" : edge > 0.12 ? "Big win" : "Slight win", tone: "success" };
  return { position, label: mode === "sim" ? "A better deal for them" : edge < -0.12 ? "Big loss" : "Slight loss", tone: "danger" };
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

/** The first content line (one row of the open tab) that must be visible under the pills at the peek height. */
export const PEEK_FIRST_LINE_PX = 52;
export const PEEK_MIN_FRAC = 0.4;
export const PEEK_MAX_FRAC = 0.7;

/**
 * Peek height in px, computed from the content (coridian_, 2026-11-14: the tab row sat clipped at the bottom of a fixed 56%
 * peek). `anchorBottom` is where the pill row ends, measured from the sheet's top with the compact header showing; the
 * sheet shows that plus one content line plus the bottom inset, clamped between 40% and 70% of the screen so it never
 * opens as a sliver or right up under the page header.
 */
export function peekSheetHeight({ anchorBottom, viewportH, bottomInset = 0 }: { anchorBottom: number; viewportH: number; bottomInset?: number }): number {
  const want = anchorBottom + PEEK_FIRST_LINE_PX + Math.max(0, bottomInset);
  return Math.round(Math.max(viewportH * PEEK_MIN_FRAC, Math.min(viewportH * PEEK_MAX_FRAC, want)));
}

/** True when the pill row is fully inside the part of the sheet that shows at `peekH` (a check for tests and the geometry script). */
export function peekShowsTabs(anchorBottom: number, peekH: number, bottomInset = 0): boolean {
  return anchorBottom <= peekH - Math.max(0, bottomInset) + 0.5;
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
