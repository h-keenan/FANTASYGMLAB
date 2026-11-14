/**
 * The universal player BADGE / SYMBOL system (docs/ui-patterns.md, "PlayerBadge"). Pure and import-free,
 * byte-identical twin of mobile/src/lib/playerBadges.ts.
 *
 * coridian_ (phone, 2026-11-14): "I don't think a rookie draft should even have a rookie tag because it's obvious; if they
 * do need tags we need some sort of symbol like Sleeper has (a purple R). We need symbols so we can stop using full words
 * that take up all the space." So every status a player row can carry (Rookie, IR, Taxi, Out, Q, Bye, Free agent, On block,
 * ...) is ONE short glyph on a small tinted badge, with an accessible full-word label that only a screen reader, a tooltip,
 * a long-press or the legend sheet shows. Three rules live here so web and app never disagree:
 *
 *  1. Fixed semantic tones (only the existing success / danger / warning / muted / accent / action tokens).
 *  2. Context suppression: a badge that is true for EVERY row of the list (Rookie in a rookie draft, Free agent on a
 *     free-agent board, IR on the IR list) says nothing, so it is not drawn (`suppress`).
 *  3. At most `max` badges per row, the rest folded into "+n" (the legend/tooltip still names them).
 */

export type BadgeTone = "success" | "danger" | "warning" | "muted" | "accent" | "action";

export type BadgeKind =
  | "rookie"
  | "ir"
  | "taxi"
  | "out"
  | "doubtful"
  | "questionable"
  | "bye"
  | "fa"
  | "block"
  | "target"
  | "starter"
  | "bench"
  | "new"
  | "captain"
  | "yours"
  | "fillin"
  | "backup";

export interface BadgeSpec {
  kind: BadgeKind;
  /** One or two characters (never a word): what is drawn on the badge. */
  glyph: string;
  tone: BadgeTone;
  /** The full word: aria-label, tooltip, legend. */
  label: string;
  /** One line for the legend sheet. */
  legend: string;
  /** Lower sorts first: severity (injury, reserve) before roles before flavour. */
  order: number;
}

export const BADGES: Readonly<Record<BadgeKind, BadgeSpec>> = {
  out: { kind: "out", glyph: "O", tone: "danger", label: "Out", legend: "Out: will not play. Tap the player for the weeks.", order: 10 },
  ir: { kind: "ir", glyph: "IR", tone: "danger", label: "Injured reserve", legend: "On injured reserve (does not count against the roster limit).", order: 11 },
  doubtful: { kind: "doubtful", glyph: "D", tone: "danger", label: "Doubtful", legend: "Doubtful: unlikely to play.", order: 12 },
  questionable: { kind: "questionable", glyph: "Q", tone: "warning", label: "Questionable", legend: "Questionable: may or may not play.", order: 13 },
  taxi: { kind: "taxi", glyph: "T", tone: "warning", label: "Taxi squad", legend: "On the taxi squad (young players stashed off the active roster).", order: 20 },
  bye: { kind: "bye", glyph: "By", tone: "muted", label: "On bye", legend: "On a bye this week.", order: 21 },
  rookie: { kind: "rookie", glyph: "R", tone: "accent", label: "Rookie", legend: "Rookie: first NFL season.", order: 30 },
  new: { kind: "new", glyph: "N", tone: "action", label: "New", legend: "New since you last looked.", order: 31 },
  fa: { kind: "fa", glyph: "FA", tone: "success", label: "Free agent", legend: "Free agent: not on any team.", order: 40 },
  block: { kind: "block", glyph: "$", tone: "action", label: "On the trade block", legend: "Listed on the trade block.", order: 41 },
  target: { kind: "target", glyph: "◎", tone: "accent", label: "Trade target", legend: "A player you are targeting.", order: 42 },
  captain: { kind: "captain", glyph: "C", tone: "action", label: "Captain", legend: "Your captain (bonus scoring).", order: 43 },
  yours: { kind: "yours", glyph: "★", tone: "accent", label: "Your player", legend: "On your team.", order: 44 },
  starter: { kind: "starter", glyph: "S", tone: "success", label: "Starter", legend: "In your starting lineup.", order: 50 },
  fillin: { kind: "fillin", glyph: "F", tone: "accent", label: "Fill-in starter", legend: "Filling in for an injured starter.", order: 51 },
  bench: { kind: "bench", glyph: "BN", tone: "muted", label: "Bench", legend: "On your bench.", order: 52 },
  backup: { kind: "backup", glyph: "BU", tone: "muted", label: "Backup", legend: "Backup: not starting right now.", order: 53 },
};

/** Default cap per row; the rest become "+n". */
export const BADGE_MAX = 3;

/** One badge to draw. `detail` is extra text only the quick view / tooltip shows ("2 wks"). */
export interface BadgeInput {
  kind: BadgeKind;
  detail?: string | null;
}

export interface ResolvedBadges {
  shown: (BadgeInput & { spec: BadgeSpec })[];
  /** How many were folded into "+n". */
  overflow: number;
  /** Names of the folded ones, for the "+n" tooltip. */
  overflowLabels: string[];
}

/** Drop duplicates (first wins) and suppressed kinds, sort by severity, cap at `max`. */
export function resolveBadges(inputs: ReadonlyArray<BadgeInput | null | undefined | false>, opts: { suppress?: ReadonlyArray<BadgeKind>; max?: number } = {}): ResolvedBadges {
  const max = Math.max(1, opts.max ?? BADGE_MAX);
  const hide = new Set(opts.suppress ?? []);
  const seen = new Set<BadgeKind>();
  const all: (BadgeInput & { spec: BadgeSpec })[] = [];
  for (const input of inputs) {
    if (!input || hide.has(input.kind) || seen.has(input.kind)) continue;
    seen.add(input.kind);
    all.push({ ...input, spec: BADGES[input.kind] });
  }
  all.sort((a, b) => a.spec.order - b.spec.order);
  const shown = all.slice(0, max);
  const rest = all.slice(max);
  return { shown, overflow: rest.length, overflowLabels: rest.map((b) => badgeTitle(b)) };
}

/** "Out: 2 wks" / "Rookie": the tooltip and screen-reader text of one badge. */
export function badgeTitle(badge: BadgeInput & { spec?: BadgeSpec }): string {
  const spec = badge.spec ?? BADGES[badge.kind];
  return badge.detail && badge.detail.toLowerCase() !== spec.label.toLowerCase() ? `${spec.label}: ${badge.detail}` : spec.label;
}

/** "Out: 2 wks, Rookie, plus 1 more: Bench": one spoken line for a whole badge group. */
export function badgesAriaLabel(r: ResolvedBadges): string {
  const parts = r.shown.map((b) => badgeTitle(b));
  if (r.overflow > 0) parts.push(`plus ${r.overflow} more: ${r.overflowLabels.join(", ")}`);
  return parts.join(", ");
}

/**
 * Context suppression. Given the badge kinds of every row currently listed, a kind that EVERY row carries (and the list
 * has at least `minRows` rows, so a one-row list still tells you what it is) is returned: it is true of the whole list,
 * so it is noise. A rookie draft board suppresses Rookie, a free-agent board suppresses FA. Health badges are never
 * suppressed (a list where everyone is Out still needs to say so).
 */
const NEVER_SUPPRESSED: ReadonlySet<BadgeKind> = new Set<BadgeKind>(["out", "doubtful", "questionable"]);

export function contextSuppressed(rows: ReadonlyArray<ReadonlyArray<BadgeKind>>, minRows = 3): BadgeKind[] {
  if (rows.length < minRows) return [];
  const counts = new Map<BadgeKind, number>();
  for (const row of rows) for (const kind of new Set(row)) counts.set(kind, (counts.get(kind) ?? 0) + 1);
  return [...counts.entries()].filter(([kind, n]) => n === rows.length && !NEVER_SUPPRESSED.has(kind)).map(([kind]) => kind);
}

/** The injury word Sleeper/our feeds send ("Questionable", "Out", "IR", "Doubtful") as a badge kind. Healthy/unknown = null. */
export function badgeFromInjury(status: string | null | undefined): BadgeKind | null {
  const s = (status ?? "").trim().toLowerCase();
  if (!s) return null;
  if (s === "q" || s.startsWith("question")) return "questionable";
  if (s === "d" || s.startsWith("doubt")) return "doubtful";
  if (s === "ir" || s.includes("injured reserve") || s === "pup" || s === "nfi") return "ir";
  if (s === "o" || s.startsWith("out") || s === "sus" || s.startsWith("suspend")) return "out";
  return null;
}

/**
 * Map a legacy `{ key, label }` tag (the free-text chips the list row used to take: "Free agent", "On block", "IR",
 * "ROOKIE") onto a badge kind, so every existing caller routes through the one badge system without each being rewritten.
 * Anything that is not a status (an owner's team name, "Hot streak") returns null and stays a text pill.
 */
export function badgeFromTag(tag: { key?: string; label?: string }): BadgeInput | null {
  const key = (tag.key ?? "").toLowerCase();
  const label = (tag.label ?? "").trim();
  const lower = label.toLowerCase();
  if (key === "block" || lower === "on block" || lower === "your block") return { kind: "block", detail: lower === "your block" ? "yours" : null };
  if (key === "rookie" || lower === "rookie") return { kind: "rookie" };
  if (key === "ir" || lower === "ir") return { kind: "ir" };
  if (key === "taxi" || lower === "taxi") return { kind: "taxi" };
  if (key === "new" || lower === "new") return { kind: "new" };
  if (key === "target") return { kind: "target" };
  if (key === "captain") return { kind: "captain" };
  if (key === "out" || /^out\b/.test(lower)) {
    const weeks = /(\d+)\s*w/.exec(lower);
    return { kind: "out", detail: weeks ? `${weeks[1]} ${weeks[1] === "1" ? "wk" : "wks"}` : null };
  }
  if (lower === "free agent" || key === "fa") return { kind: "fa" };
  if (lower === "your team") return { kind: "yours" };
  if (key === "role") {
    if (lower.includes("fill")) return { kind: "fillin" };
    if (lower.includes("backup")) return { kind: "backup" };
  }
  const injury = badgeFromInjury(label);
  if (injury) return { kind: injury };
  return null;
}

/** The legend rows in display order (legend sheet). */
export function badgeLegend(kinds?: ReadonlyArray<BadgeKind>): BadgeSpec[] {
  const list = kinds ? kinds.map((k) => BADGES[k]) : Object.values(BADGES);
  return [...list].sort((a, b) => a.order - b.order);
}
