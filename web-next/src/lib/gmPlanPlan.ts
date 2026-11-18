/**
 * GM Plan Overview, concept C: the four stat tiles, the numbered action steps, and the "why this stance" line.
 * Pure and import-free, byte-identical twin of mobile/src/lib/gmPlanPlan.ts. Everything here is derived from data the page
 * already has (the Plan Snapshot tiles, the declared stance, the GM Plan focus areas); nothing is invented.
 */

export type PlanStance = "rebuilding" | "competing" | "balanced" | "";

type SnapshotLike = { key: string; value: string; fill?: number | null };

export interface PlanFacts {
  power: { rank: number; total: number } | null;
  capital: { rank: number; total: number } | null;
  oddsPct: number | null;
  record: string | null;
}

export function ordinal(n: number): string {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
  switch (n % 10) {
    case 1:
      return `${n}st`;
    case 2:
      return `${n}nd`;
    case 3:
      return `${n}rd`;
    default:
      return `${n}th`;
  }
}

function parseRank(value: string | undefined): { rank: number; total: number } | null {
  const m = /^(\d+) of (\d+)$/.exec((value ?? "").trim());
  return m ? { rank: Number(m[1]), total: Number(m[2]) } : null;
}

export function planFacts(snapshot: readonly SnapshotLike[]): PlanFacts {
  const byKey = new Map(snapshot.map((t) => [t.key, t]));
  const odds = /^(\d+)%$/.exec((byKey.get("odds")?.value ?? "").trim());
  const record = byKey.get("record")?.value;
  return {
    power: parseRank(byKey.get("power")?.value),
    capital: parseRank(byKey.get("capital")?.value),
    oddsPct: odds ? Number(odds[1]) : null,
    record: record ? record.replace(/\s+/g, "") : null,
  };
}

export interface PlanStatTile {
  key: "power" | "capital" | "odds" | "record";
  glyph: "power" | "franchise" | "record";
  label: string;
  value: string;
  note?: string;
}

/** The four headline tiles, in order, each only when its data exists ("11th" + "of 12", "0%", "3-7"). */
export function planStatTiles(snapshot: readonly SnapshotLike[]): PlanStatTile[] {
  const f = planFacts(snapshot);
  const tiles: PlanStatTile[] = [];
  if (f.power) tiles.push({ key: "power", glyph: "power", label: "This season", value: ordinal(f.power.rank), note: `of ${f.power.total}` });
  if (f.capital) tiles.push({ key: "capital", glyph: "franchise", label: "Draft capital", value: ordinal(f.capital.rank), note: `of ${f.capital.total}` });
  if (f.oddsPct !== null) tiles.push({ key: "odds", glyph: "record", label: "Playoff odds", value: `${f.oddsPct}%` });
  if (f.record) tiles.push({ key: "record", glyph: "record", label: "Record", value: f.record });
  return tiles;
}

export interface PlanStepChip {
  label: string;
  tone: "accent" | "success" | "muted";
}

export interface PlanStep {
  key: string;
  title: string;
  summary: string;
  chip: PlanStepChip | null;
  /** "trades" nests the trade ideas; "area" nests that focus area's items; "plain" has no body. */
  kind: "trades" | "area" | "plain";
  areaKey?: string;
}

export interface PlanAreaInput {
  key: string;
  title: string;
  framing: string;
  count: number;
  hasSignal: boolean;
}

const TRADE_TITLE: Record<string, string> = {
  rebuilding: "Sell aging vets for picks",
  competing: "Buy upgrades for the stretch run",
  balanced: "Make value-positive trades",
};

const CAPITAL_TITLE: Record<string, string> = {
  rebuilding: "Stack draft capital",
  competing: "Use picks as trade currency",
  balanced: "Keep your picks flexible",
};

export function planStepSummaryPartners(partners: readonly string[]): string {
  const clean = partners.map((p) => p.trim()).filter(Boolean);
  if (clean.length === 0) return "";
  if (clean.length <= 2) return clean.join(" and ");
  return `${clean[0]}, ${clean[1]} +${clean.length - 2}`;
}

/** The numbered steps: the stance's trade move (trades nested), the draft-capital move, then each focus area with a signal. */
export function buildPlanSteps(input: {
  stance: PlanStance;
  tradeCount: number;
  partners: readonly string[];
  topConfidence: string | null;
  capital: { rank: number; total: number } | null;
  areas: readonly PlanAreaInput[];
}): PlanStep[] {
  const steps: PlanStep[] = [];
  const { stance } = input;
  steps.push({
    key: "trades",
    title: TRADE_TITLE[stance] ?? "Review your trade ideas",
    summary:
      input.tradeCount === 0
        ? "No trade ideas right now"
        : `${input.tradeCount} idea${input.tradeCount === 1 ? "" : "s"}: ${planStepSummaryPartners(input.partners)}`,
    chip: input.topConfidence ? { label: input.topConfidence, tone: "accent" } : null,
    kind: "trades",
  });
  if (input.capital) {
    const { rank, total } = input.capital;
    const top = rank <= Math.ceil(total / 3);
    steps.push({
      key: "capital",
      title: CAPITAL_TITLE[stance] ?? "Know your draft capital",
      summary: rank === 1 ? "You hold the most draft capital in the league" : `Your draft capital ranks ${ordinal(rank)} of ${total}`,
      chip: { label: ordinal(rank), tone: top ? "success" : "muted" },
      kind: "plain",
    });
  }
  for (const area of input.areas) {
    // The standing facts (rank, record) are the stat tiles above the steps, so they are not a step of their own.
    if (!area.hasSignal || area.key === "standing") continue;
    steps.push({
      key: `area-${area.key}`,
      title: area.title,
      summary: area.framing || `${area.count} signal${area.count === 1 ? "" : "s"}`,
      chip: { label: `${area.count}`, tone: "muted" },
      kind: "area",
      areaKey: area.key,
    });
  }
  return steps;
}

export interface PlanWhy {
  title: string;
  headline: string;
  bullets: string[];
}

const WHY_TITLE: Record<string, string> = { rebuilding: "Why rebuild", competing: "Why compete", balanced: "Why stay balanced" };
const WHY_TAIL: Record<string, string> = { rebuilding: "sell now, buy youth", competing: "push for the title now", balanced: "keep both paths open" };

/** The why-this-stance line and its supporting facts; null without a declared stance. */
export function buildPlanWhy(stance: PlanStance, facts: PlanFacts, deadlineWeek: number | null): PlanWhy | null {
  if (!stance) return null;
  const lead = [facts.oddsPct !== null ? `${facts.oddsPct}% playoff odds` : null, facts.record].filter(Boolean).join(", ");
  const headline = lead ? `${lead}: ${WHY_TAIL[stance]}` : WHY_TAIL[stance][0].toUpperCase() + WHY_TAIL[stance].slice(1);
  const bullets: string[] = [];
  if (facts.power) bullets.push(`You are ${ordinal(facts.power.rank)} of ${facts.power.total}${facts.oddsPct !== null ? ` with a ${facts.oddsPct}% shot at the playoffs` : ""}.`);
  if (facts.capital) bullets.push(`Your draft capital ranks ${ordinal(facts.capital.rank)} of ${facts.capital.total}.`);
  if (deadlineWeek !== null) bullets.push(`The trade deadline is Wk ${deadlineWeek}, so the market is most active now.`);
  return { title: WHY_TITLE[stance], headline, bullets };
}
