/**
 * THE module template catalog (docs/ui-patterns.md, "Module templates"). Import-free, byte-identical twin of
 * mobile/src/lib/moduleTemplates.ts. Every page is a short stack of these templates; nothing builds its own card chrome.
 * Each template records its purpose, required props, what its COLLAPSED form must show, and its density tier, so a
 * lint-style test can hold every page to it ("no modules that give no information in compact mode").
 *
 * The collapsed-form rule: a collapsed module must render at least `MIN_COLLAPSED_CHARS` characters of real data (a
 * summary string built from `parts`), never a bare title. `collapsedVerdict` is the one check; the component tests,
 * the page tests and the source scan in `moduleTemplates.test.ts(x)` all use it.
 */

import { compactParts, compactSummaryText, type CompactPart, type CompactTone } from "./compactModule";

export type DensityTier = "T0" | "T1" | "T2" | "T3" | "T4";

export type TemplateId =
  | "hero"
  | "statusHeader"
  | "matchup"
  | "recapCard"
  | "compactModule"
  | "statStrip"
  | "row"
  | "sectionHeader"
  | "actionBar"
  | "listFilter"
  | "tabPage"
  | "state"
  | "trendChart"
  | "insightLink";

export interface ModuleTemplateSpec {
  id: TemplateId;
  name: string;
  purpose: string;
  /** Props a caller must pass (names as in the web component; the app twin uses the same names, `testID` for `testId`). */
  required: string[];
  /** What the collapsed / minimal form must show. */
  collapsed: string;
  /** Density tier (docs/audits/2026-11-information-architecture.md R6) and the pixel range of the collapsed form. */
  tier: DensityTier;
  minHeight: number;
  maxHeight: number | null;
  web: string;
  app: string;
  /** Collapsed form must carry a summary string (checked by `collapsedVerdict`). False for chrome with no collapsed form. */
  summarised: boolean;
}

export const MODULE_TEMPLATES: readonly ModuleTemplateSpec[] = [
  {
    id: "hero",
    name: "Hero",
    purpose: "The one thing the page is about: one big number or status, one line of context, an optional trend.",
    required: ["label", "value", "context"],
    collapsed: "Always expanded: value + context line (never an empty frame); trend is a sparkline or a signed delta.",
    tier: "T2",
    minHeight: 88,
    maxHeight: 120,
    web: "components/ui/ModuleTemplates.tsx#Hero",
    app: "components/ModuleTemplates.tsx#Hero",
    summarised: true,
  },
  {
    id: "statusHeader",
    name: "StatusHeader (players-first)",
    purpose: "Top of Today, My Team and Sim Home: status ring + three mini stats, a 'Needs your attention' list of player rows with avatars, the one cyan primary action, optional CompactModules.",
    required: ["kicker", "headline", "attention"],
    collapsed: "Always open: ring, headline, context, at most 3 stats and 3 player rows; hidden when there is nothing to say.",
    tier: "T2",
    minHeight: 120,
    maxHeight: 420,
    web: "components/ui/StatusHeader.tsx",
    app: "components/StatusHeader.tsx",
    summarised: true,
  },
  {
    id: "matchup",
    name: "Matchup hero / ticker",
    purpose: "One matchup model, two forms: the page hero (score, win chance, bar, swing players with avatars) and the one-line ticker for stacks.",
    required: ["scores", "winChance"],
    collapsed: "Ticker: 'WK 7 · You 112.4 - 98.1 Mike · 71%'; the hero is always open.",
    tier: "T2",
    minHeight: 48,
    maxHeight: 320,
    web: "components/ui/MatchupModule.tsx",
    app: "components/MatchupModule.tsx",
    summarised: true,
  },
  {
    id: "recapCard",
    name: "RecapCard",
    purpose: "A story page or review block as one card: kicker, optional grade/finish badge, three label/value rows (more behind a tap).",
    required: ["kicker", "rows"],
    collapsed: "Always shows its three rows; extra rows sit behind 'More'.",
    tier: "T1",
    minHeight: 120,
    maxHeight: 260,
    web: "components/ui/RecapCard.tsx",
    app: "components/RecapCard.tsx",
    summarised: true,
  },
  {
    id: "compactModule",
    name: "CompactModule / CompactSummary",
    purpose: "The base card for every dense block: informative while collapsed, tap to expand inline or into a Sheet.",
    required: ["id", "title", "parts"],
    collapsed: "Title + a one or two line summary of key numbers and status (parts); optional single trailing action.",
    tier: "T0",
    minHeight: 56,
    maxHeight: 96,
    web: "components/ui/CompactModule.tsx",
    app: "components/CompactModule.tsx",
    summarised: true,
  },
  {
    id: "statStrip",
    name: "StatStrip",
    purpose: "One row of small glass tiles (rank, record, age), each a link to what explains it; one tap on 'Rank bars' expands the same stats into labelled standing bars.",
    required: ["items"],
    collapsed: "The tiles are always visible (never an empty header): 'Power #3 · Starters #5 · Age 26.1'; expanded adds rank bars.",
    tier: "T3",
    minHeight: 64,
    maxHeight: null,
    web: "components/StatStrip.tsx + ui/ModuleTemplates.tsx#StatStripModule",
    app: "components/DashboardStatRow.tsx + ModuleTemplates.tsx#StatStripModule",
    summarised: true,
  },
  {
    id: "row",
    name: "Row (player / team / pick / trade asset)",
    purpose: "One list line: lead, name, chip line under the name, one trailing action or number.",
    required: ["name", "chips"],
    collapsed: "Name plus at least one meta or chip; the right edge holds a single action or number.",
    tier: "T1",
    minHeight: 56,
    maxHeight: 72,
    web: "components/PlayerListRow.tsx, PickRow.tsx, ui/StructuredRow.tsx",
    app: "components/PlayerListRow.tsx, DraftPickAssetRow.tsx",
    summarised: false,
  },
  {
    id: "sectionHeader",
    name: "Section header",
    purpose: "Titles a group of rows. Never alone: a header with no rows or summary is not rendered.",
    required: ["title"],
    collapsed: "Title plus a count or one-line context when the section can collapse.",
    tier: "T0",
    minHeight: 44,
    maxHeight: 56,
    web: "components/SectionHeading.tsx",
    app: "components/SectionHeading.tsx",
    summarised: false,
  },
  {
    id: "actionBar",
    name: "ActionBar",
    purpose: "The one sticky strip of primary actions at the bottom of a screen (Compare, Add to trade, Draft).",
    required: ["actions"],
    collapsed: "At most 3 actions, each a labelled 44px button; hidden when there is nothing to act on.",
    tier: "T0",
    minHeight: 56,
    maxHeight: 64,
    web: "components/SimActionBar.tsx, .bottom-stack",
    app: "components/QuickActionsGrid.tsx",
    summarised: false,
  },
  {
    id: "listFilter",
    name: "List + FilterRow",
    purpose: "A list under ONE control row: search, primary pills, Sort, and a Filters button for everything else.",
    required: ["options", "onSelect"],
    collapsed: "One 44px row; extra filters live behind FilterSheet with a count badge.",
    tier: "T0",
    minHeight: 44,
    maxHeight: 44,
    web: "components/PillRow.tsx + ui/FilterSheet.tsx",
    app: "components/FilterSheet.tsx",
    summarised: false,
  },
  {
    id: "tabPage",
    name: "TabPage shell",
    purpose: "A page in a family: exactly one tab row (the family strip), then modules. Internal views are sections, never tabs.",
    required: ["family", "active"],
    collapsed: "One tab row of 2 to 5 tabs; no second PillRow used as tabs on the same page.",
    tier: "T0",
    minHeight: 44,
    maxHeight: 56,
    web: "components/PageTabBar.tsx",
    app: "components/SegmentedTabBar.tsx",
    summarised: false,
  },
  {
    id: "state",
    name: "Empty / Error / Loading",
    purpose: "The three non-data states of any module: say what is missing and the one next step.",
    required: ["title"],
    collapsed: "A title plus a reason; Loading is a Skeleton the height of the module it replaces.",
    tier: "T1",
    minHeight: 56,
    maxHeight: 120,
    web: "components/EmptyState.tsx, ErrorState.tsx, Skeleton.tsx",
    app: "components/EmptyState.tsx, ErrorState.tsx",
    summarised: false,
  },
  {
    id: "trendChart",
    name: "TrendChart usage",
    purpose: "Every trend is ui/TrendChart. Compact modules use variant=compact (axis-free sparkline) beside the number.",
    required: ["points", "name"],
    collapsed: "Sparkline next to a number or signed delta; never a chart with no number.",
    tier: "T2",
    minHeight: 40,
    maxHeight: 120,
    web: "components/ui/TrendChart.tsx",
    app: "components/TrendChart.tsx",
    summarised: false,
  },
  {
    id: "insightLink",
    name: "InsightLink",
    purpose: "Any stat about the league links to where it is explained (lib/insightLinks.ts). Collapsed text is the link or the expander.",
    required: ["insight", "league"],
    collapsed: "The stat itself, tappable; never dead text.",
    tier: "T0",
    minHeight: 44,
    maxHeight: null,
    web: "components/ui/InsightLink.tsx",
    app: "components/InsightRow.tsx",
    summarised: false,
  },
];

/** Fantasy Sim modules are thin adapters over the templates above (no template of their own). */
export const SIM_TEMPLATE_ADAPTERS: ReadonlyArray<{ module: string; template: TemplateId; note: string }> = [
  { module: "SimFold", template: "compactModule", note: "CompactModule with sim parts (simSummaries.ts)" },
  { module: "SimDraftHero", template: "hero", note: "on-the-clock Hero + CompactModule bar (simDraft.ts); the bar's `preview` line is SimDraftBar (best-available avatar, position, letter grade)" },
  { module: "SimStatusHeader", template: "statusHeader", note: "Home: ring = win chance, injuries/waiver/bye player rows (projection and ADP only)" },
  { module: "SimDraftRow / SimPlayerLine / SimRosterLine", template: "row", note: "PlayerAccordionRow mode=sim: stats line with PROJ and a grade tile, one Move button that expands the row into an action strip" },
  { module: "SimDraftBoard filters", template: "listFilter", note: "one control row: position pills + sort" },
  { module: "SimActionBar", template: "actionBar", note: "sticky sim actions" },
  { module: "SimNotice", template: "state", note: "auto-dismiss notice toast (noticeDismissMs)" },
  { module: "SimGameHome modules (inbox, waivers, injuries, byes, standings)", template: "compactModule", note: "simInboxParts, simWaiverParts, simInjuryParts, simByeParts, simStandingsParts" },
  { module: "SimGameTeamSheet / SimPlayerSheet", template: "tabPage", note: "Sheet tabs plan (sheetTabs.ts), sim plans isolated" },
];

/** A collapsed module shows at least this many characters of real data (summary string), or it is an empty header. */
export const MIN_COLLAPSED_CHARS = 12;

/** Strings that look like data but carry none. */
const PLACEHOLDER = /^(—|-|–|n\/a|none|\.\.\.|loading…?|loading\.\.\.)$/i;

export interface CollapsedVerdict {
  ok: boolean;
  chars: number;
  summary: string;
  reason?: string;
}

/**
 * The lint-style check: does the collapsed form of a module give information? `parts` is what the module passes to
 * `CompactModule`. Placeholders ("—", "Loading…") do not count. Titles never count.
 */
export function collapsedVerdict(
  parts: ReadonlyArray<CompactPart | null | undefined | false | "">,
  min: number = MIN_COLLAPSED_CHARS,
): CollapsedVerdict {
  const real = compactParts(parts).filter((p) => !PLACEHOLDER.test(p.text.trim()));
  const summary = compactSummaryText(real);
  if (real.length === 0) return { ok: false, chars: 0, summary, reason: "no summary parts: an empty header" };
  if (summary.length < min) return { ok: false, chars: summary.length, summary, reason: `summary shorter than ${min} characters` };
  return { ok: true, chars: summary.length, summary };
}

export interface TemplateCatalogIssue {
  id: string;
  problem: string;
}

/** Self-check of the catalog (used by the lib test): unique ids, every field filled, sane height ranges. */
export function catalogIssues(catalog: readonly ModuleTemplateSpec[] = MODULE_TEMPLATES): TemplateCatalogIssue[] {
  const issues: TemplateCatalogIssue[] = [];
  const seen = new Set<string>();
  for (const t of catalog) {
    if (seen.has(t.id)) issues.push({ id: t.id, problem: "duplicate id" });
    seen.add(t.id);
    if (!t.purpose.trim()) issues.push({ id: t.id, problem: "no purpose" });
    if (!t.collapsed.trim()) issues.push({ id: t.id, problem: "no collapsed-form rule" });
    if (t.required.length === 0) issues.push({ id: t.id, problem: "no required props" });
    if (t.maxHeight != null && t.maxHeight < t.minHeight) issues.push({ id: t.id, problem: "max height below min height" });
    if (t.minHeight < 40) issues.push({ id: t.id, problem: "below the 44px touch target guidance" });
    if (!t.web || !t.app) issues.push({ id: t.id, problem: "missing web or app twin" });
  }
  return issues;
}

export interface StatPartInput {
  /** Short label used in the line: "Power", "Starters", "Age". */
  label: string;
  /** Formatted value: "#3", "26.1", "7-2". Empty / "—" values are dropped. */
  value: string;
  tone?: CompactTone;
  strong?: boolean;
}

/** Collapsed summary of a stat strip: "Power #3 · Starters #5 · Age 26.1". Placeholder values are dropped. */
export function statStripParts(items: readonly StatPartInput[], max: number = 4): CompactPart[] {
  const out: CompactPart[] = [];
  for (const item of items) {
    const value = (item.value ?? "").trim();
    if (!value || PLACEHOLDER.test(value)) continue;
    out.push({ key: item.label, text: `${item.label} ${value}`, tone: item.tone, strong: item.strong });
    if (out.length >= max) break;
  }
  return out;
}

/**
 * Collapsed summary of a list module: the count, then what is first or most urgent.
 * `listSummaryParts({ count: 3, noun: "alert", highlights: ["Injury: Gibbs"] })` -> "3 alerts · Injury: Gibbs".
 */
export function listSummaryParts(input: {
  count: number;
  noun: string;
  plural?: string;
  none?: string;
  highlights?: ReadonlyArray<string | null | undefined | false>;
  tone?: CompactTone;
  maxHighlights?: number;
}): CompactPart[] {
  const { count, noun, plural, none, highlights = [], tone, maxHighlights = 2 } = input;
  const head: CompactPart =
    count <= 0
      ? { key: "count", text: none ?? `No ${plural ?? `${noun}s`}`, tone: "muted" }
      : { key: "count", text: `${count} ${count === 1 ? noun : (plural ?? `${noun}s`)}`, tone, strong: true };
  const rest = highlights
    .filter((h): h is string => typeof h === "string" && h.trim().length > 0)
    .slice(0, maxHighlights)
    .map((text, i) => ({ key: `h${i}`, text }));
  return [head, ...rest];
}

export type TrendDirection = "up" | "down" | "flat";

export interface TrendModel {
  direction: TrendDirection;
  delta: number;
  /** "+2.1", "-3", "Flat". */
  label: string;
  tone: CompactTone;
}

/**
 * The trend of a Hero from its recent points (oldest first). `higherIsBetter=false` for ranks. Fewer than two
 * numeric points: null (the Hero then shows no trend rather than a fake one).
 */
export function trendModel(points: ReadonlyArray<number | null | undefined>, higherIsBetter: boolean = true, digits: number = 1): TrendModel | null {
  const nums = points.filter((p): p is number => typeof p === "number" && Number.isFinite(p));
  if (nums.length < 2) return null;
  const delta = nums[nums.length - 1] - nums[0];
  const rounded = Number(delta.toFixed(digits));
  if (rounded === 0) return { direction: "flat", delta: 0, label: "Flat", tone: "muted" };
  const up = rounded > 0;
  const good = up === higherIsBetter;
  return {
    direction: up ? "up" : "down",
    delta: rounded,
    label: `${up ? "+" : ""}${rounded.toFixed(digits).replace(/\.0+$/, "")}`,
    tone: good ? "success" : "danger",
  };
}

/** Summary parts for a Hero's accessible name and tests: "Team value 71 · Top 3rd of 12 · +4". */
export function heroParts(input: { label: string; value: string; context?: string | null; trend?: TrendModel | null }): CompactPart[] {
  return compactParts([
    { key: "value", text: `${input.label} ${input.value}`.trim(), strong: true },
    input.context ? { key: "context", text: input.context } : null,
    input.trend ? { key: "trend", text: input.trend.label, tone: input.trend.tone } : null,
  ]);
}
