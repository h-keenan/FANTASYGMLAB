// Twin file: web-next/src/lib/appHeader.ts and mobile/src/lib/appHeader.ts stay identical.
//
// THE header rules (UI pass 7 / docs/audits/2026-11-header-rewrite.md; coridian_ picked direction V2, the context ribbon). Pure: no React, no DOM.
//
// Rule 1, a label appears once: the bottom pill (and its family strip) already names a tab page, so a tab page's header does not
// repeat the name. It carries league identity and a ribbon of glanceable chips instead. Only pages nothing else names (detail pages,
// settings, sheets) carry a title.

export type HeaderTemplate = "root" | "detail" | "sheet" | "immersive" | "sim";

/** Route segments the bottom pill / family strip names. Their header is the root template and shows no title. */
export const TAB_PAGE_SEGMENTS: readonly string[] = [
  "dashboard",
  "my-team",
  "players",
  "waivers",
  "matchup",
  "trade-hub",
  "trade-finder",
  "trade-analyzer",
  "trade-history",
  "league-rankings",
  "league-recaps",
  "games",
  "news",
  "portfolio",
  "leagues",
];

const firstSegment = (pathname: string | null | undefined) => (pathname || "").split("/").filter(Boolean)[0] ?? "";

/** Which header template a route uses. */
export function headerTemplateFor(pathname: string | null | undefined): HeaderTemplate {
  const segment = firstSegment(pathname);
  if (segment === "gm-game") return "sim";
  if (segment === "" || segment === "onboarding" || segment === "premium" || segment === "connect-league") return "immersive";
  // `/players/<leagueId>/<playerId>` is a detail page of the Players tab.
  if (segment === "players" && (pathname || "").split("/").filter(Boolean).length > 2) return "detail";
  return TAB_PAGE_SEGMENTS.includes(segment) ? "root" : "detail";
}

/** Whether the header shows the page's name (root pages do not: the pill names them). */
export function headerShowsTitle(pathname: string | null | undefined): boolean {
  return headerTemplateFor(pathname) !== "root";
}

export type HeaderChipTone = "accent" | "success" | "danger" | "warning" | "muted";
export type HeaderChip = { key: string; text: string; tone?: HeaderChipTone };

export const MAX_HEADER_CHIPS = 4;

const norm = (s: string) => s.trim().toLowerCase().replace(/\s+/g, " ");

/**
 * The ribbon chips a page may show: empty text dropped, duplicates dropped, a chip that just repeats the page's label or the league
 * name dropped (rule 1), at most MAX_HEADER_CHIPS, the first one in the accent tone.
 */
export function normalizeHeaderChips(chips: ReadonlyArray<HeaderChip | null | undefined> | null | undefined, avoid: ReadonlyArray<string | null | undefined> = []): HeaderChip[] {
  const banned = new Set(avoid.filter((a): a is string => Boolean(a)).map(norm));
  const seen = new Set<string>();
  const out: HeaderChip[] = [];
  for (const chip of chips ?? []) {
    if (!chip) continue;
    const text = chip.text.trim();
    const key = norm(text);
    if (!text || banned.has(key) || seen.has(key)) continue;
    seen.add(key);
    out.push({ ...chip, text, tone: chip.tone ?? (out.length === 0 ? "accent" : undefined) });
    if (out.length >= MAX_HEADER_CHIPS) break;
  }
  return out;
}

/** Rule 1 check used by tests and the guard: does this header title repeat a label the page already shows (pill, family tab)? */
export function repeatsLabel(title: string | null | undefined, labels: ReadonlyArray<string | null | undefined>): boolean {
  const t = norm(title ?? "");
  return t.length > 0 && labels.some((l) => norm(l ?? "") === t);
}

/** Scroll distance (px) after which the ribbon folds into the first row. */
export const HEADER_COLLAPSE_AT = 24;
/** Whether the ribbon is collapsed at a scroll offset. A little hysteresis (the ribbon returns only near the top) stops flicker. */
export function ribbonCollapsed(scrollY: number, wasCollapsed: boolean): boolean {
  if (wasCollapsed) return scrollY > 4;
  return scrollY > HEADER_COLLAPSE_AT;
}

/** Leagues matching a search, case-insensitive on the name; the current league first. Used by the switcher sheet (search shows from 6 leagues). */
export const SWITCHER_SEARCH_FROM = 6;
export function filterLeagues<T extends { league_id: string; league_name: string | null }>(rows: readonly T[], query: string, currentId: string | null): T[] {
  const q = norm(query);
  const hit = q ? rows.filter((r) => norm(r.league_name ?? r.league_id).includes(q)) : [...rows];
  return hit.sort((a, b) => (a.league_id === currentId ? -1 : b.league_id === currentId ? 1 : 0));
}

/** The ribbon chips a status header (Today, Team) implies: the ring as "Win 57%", then each mini stat as "Standing value" / "Label value". */
export function chipsFromStatus(model: {
  ring?: { pct?: number | null; label: string; tone?: HeaderChipTone } | null;
  stats: ReadonlyArray<{ key: string; label: string; value: string; tone?: HeaderChipTone }>;
}): HeaderChip[] {
  const out: HeaderChip[] = [];
  if (model.ring && model.ring.pct != null) out.push({ key: "ring", text: /win/i.test(model.ring.label) ? `Win ${model.ring.pct}%` : model.ring.label, tone: model.ring.tone });
  for (const s of model.stats) {
    if (!s.value?.trim()) continue;
    out.push({ key: s.key, text: /^(standing|record|team|power)$/i.test(s.label) ? s.value : `${s.label} ${s.value}`, tone: s.tone });
  }
  return out;
}
