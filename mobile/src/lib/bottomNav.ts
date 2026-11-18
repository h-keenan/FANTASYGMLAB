import type { TabIconName } from "./tabIcons";

/**
 * Pure logic for the phone bottom tab bar (web components/ui/BottomTabBar.tsx,
 * mobile components/BottomTabBar.tsx). Byte-identical lib twin
 * (scripts/check_lib_twins.mjs): the tab lists, badge text and which paths
 * own a bottom bar live here once so the two platforms cannot drift.
 */

export type BottomTab = {
  key: string;
  label: string;
  glyph: TabIconName;
  /** Count shown on the tab (0 or undefined hides it). */
  badge?: number;
  /** What the count is made of ("2 waiver results, 1 new injury"); read out instead of the bare number. */
  badgeSummary?: string;
  /** Route for tabs that navigate (the site shell); in-page tabs leave it off. */
  href?: string;
  /** Paid tab: the bar shows the Pro marker (to anyone not on Pro) before the tap, same as the More rows. */
  pro?: boolean;
};

/** 44px is the smallest tap target the bar may render. */
export const BOTTOM_BAR_MIN_TARGET_PX = 44;

/** "" never shows; 1 to 9 as is; 10 and up as "9+" so the badge keeps its shape. */
export function bottomTabBadgeText(count: number | null | undefined): string | null {
  if (!count || count < 1 || !Number.isFinite(count)) return null;
  return count > 9 ? "9+" : String(Math.floor(count));
}

/** Accessible name: the label plus the count in words, so a badge is never icon-only. `showPro` adds ", Pro feature" for a paid tab. */
export function bottomTabAriaLabel(tab: Pick<BottomTab, "label" | "badge" | "pro" | "badgeSummary">, showPro = false): string {
  const text = bottomTabBadgeText(tab.badge);
  const base = text ? `${tab.label}, ${tab.badgeSummary || `${Math.floor(tab.badge ?? 0)} new`}` : tab.label;
  return showPro && tab.pro ? `${base}, Pro feature` : base;
}

/** Whether a tab wears the Pro marker: it is paid and the person is known not to be on Pro (pass `useIsPro() === false`). */
export function tabShowsPro(tab: Pick<BottomTab, "pro"> | Pick<PillContextTab, "pro">, notPro: boolean): boolean {
  return Boolean(tab.pro && notPro);
}

/** The Fantasy Sim game's bottom tabs. The offseason has no Players tab and calls Home "Offseason". */
export function simGameBottomTabs(opts: { offseason?: boolean; inbox?: number }): BottomTab[] {
  const trades: BottomTab = { key: "trades", label: "Trades", glyph: "trades", badge: opts.inbox ?? 0 };
  if (opts.offseason) {
    return [
      { key: "home", label: "Offseason", glyph: "home" },
      { key: "team", label: "Team", glyph: "team" },
      trades,
      { key: "league", label: "League", glyph: "league" },
    ];
  }
  return [
    { key: "home", label: "Home", glyph: "home" },
    { key: "team", label: "Team", glyph: "team" },
    { key: "players", label: "Players", glyph: "players" },
    trades,
    { key: "league", label: "League", glyph: "league" },
  ];
}

export type SimNavTone = "accent" | "success" | "warning" | "danger" | "premium";

/** One-line description and accent tone per game page, so the game menu rows read like FantasyDesk's More sheet (glyph tinted, label over a subtitle). Tones are existing semantic colors on both platforms. */
export const SIM_NAV_META: Record<string, { subtitle: string; tone: SimNavTone }> = {
  home: { subtitle: "This week's to-dos and the league pulse", tone: "accent" },
  team: { subtitle: "Lineup, bench, and roster moves", tone: "success" },
  players: { subtitle: "Free agents, rankings, and waivers", tone: "warning" },
  trades: { subtitle: "Offers, ideas, and the trade inbox", tone: "danger" },
  league: { subtitle: "Standings, scores, and every team", tone: "premium" },
  more: { subtitle: "Rules, reset the week, or leave this game", tone: "accent" },
};

/** Which tab is lit: unknown keys fall back to the first tab. */
export function activeBottomTab(tabs: BottomTab[], active: string): string {
  return tabs.some((t) => t.key === active) ? active : (tabs[0]?.key ?? "");
}

export type SimStatusChip = { key: string; label: string; tone: "warning" | "accent"; tab: "team" | "trades" };

/** The two pre-advance notes as small tappable chips (a lineup issue and trade offers about to expire). */
export function simStatusChips(pending: { lineup_warnings?: number; inbox?: number } | null | undefined, game?: { auto_manage?: boolean; lineup_edited?: boolean }): SimStatusChip[] {
  const out: SimStatusChip[] = [];
  // Auto-manage sets the best healthy lineup when the week plays (unless this week's was set by hand), so those issues are not counted.
  const w = game?.auto_manage && !game.lineup_edited ? 0 : (pending?.lineup_warnings ?? 0);
  const inbox = pending?.inbox ?? 0;
  if (w > 0) out.push({ key: "lineup", label: `${w} lineup issue${w === 1 ? "" : "s"}`, tone: "warning", tab: "team" });
  if (inbox > 0) out.push({ key: "offers", label: `${inbox} offer${inbox === 1 ? "" : "s"} expiring`, tone: "accent", tab: "trades" });
  return out;
}

/** "Wk 3/14" for the one-line game header; playoffs and the offseason read as their own word. */
export function simCompactWeek(game: { phase: string; week: number; settings?: { regular_weeks?: number } }): string {
  if (game.phase === "draft") return "Draft";
  if (game.phase === "complete") return "Final";
  if (game.phase === "offseason") return "Offseason";
  if (game.phase === "playoffs") return `Playoffs Wk ${game.week}`;
  const total = game.settings?.regular_weeks;
  return total ? `Wk ${game.week}/${total}` : `Wk ${game.week}`;
}

/** "S3 2028" season chip for dynasty games (the shared season label; "S3/10" when the game has no calendar year); empty for a redraft. */
export function simCompactSeason(dynasty: { season_no: number; seasons: number; year?: number | null; season_label?: string | null } | null | undefined): string {
  if (!dynasty) return "";
  if (dynasty.season_label) return dynasty.season_label;
  return dynasty.year ? `S${dynasty.season_no} ${dynasty.year}` : `S${dynasty.season_no}/${dynasty.seasons}`;
}

/** Paths whose page renders its own phone chrome (compact header plus bottom bar), so the global header and the GM orb button step aside below 768px. */
export function pathOwnsPhoneChrome(pathname: string | null | undefined): boolean {
  const p = pathname || "";
  return p === "/gm-game" || p.startsWith("/gm-game/");
}

/** Accessible name of the game orb: the page you are on, plus pending trade offers. */
export function simOrbAriaLabel(currentLabel: string, inbox: number | null | undefined): string {
  const n = Math.floor(inbox ?? 0);
  // Starts with what the orb shows (the page name, then the badge), matching web (WCAG 2.5.3 Label in Name).
  const shown = n > 9 ? "9+" : String(n);
  return n > 0 ? `${currentLabel} ${shown}. Game menu, ${n} trade offer${n === 1 ? "" : "s"} waiting` : `${currentLabel}. Game menu`;
}

// ---- Smart pill: page context (web components/BottomPillContext.tsx + BottomTabBar; mobile components/BottomPill.tsx) ----

/** One page-level tab shown in the pill's page segment (the page-family tabs: Lineup | Players | Waivers | Matchup). */
export type PillContextTab = { key: string; label: string; /** Paid tab: wears the Pro marker for anyone not on Pro. */ pro?: boolean; /** Short form for the tight pill ("Hist."); the full label stays the accessible name. */ short?: string; glyph?: TabIconName; badge?: number; /** App only: a long-press quick action ("Trades" -> "New trade"). Web tabs are links (iOS long-press opens the preview sheet), so web ignores it. */ shortcut?: TabShortcut; /** Web: the tab is a route, rendered as a link (client navigation, opens in a new tab on demand). onSelect still fires. */ href?: string };

/** The one primary action of a page (Auto-set, New trade, Claim). Rendered as the accent chip at the end of the segment. */
export type PillContextAction = { key: string; label: string; glyph?: TabIconName; disabled?: boolean; busy?: boolean; onPress: () => void; /** Web: render as a link to this route (onPress still fires). */ href?: string; /** "warning": the chip is amber (a lineup issue to see BEFORE advancing). Never red. */ tone?: "warning" };

/**
 * What a page registers with the pill: its page tabs, which one is lit, and one primary action. The page owns the
 * state; the pill only renders it. A page that registers no context leaves the pill as the plain global tabs.
 */
export type PillContext = {
  /** Stable id of the page ("team", "trades", "sim-draft"): a change replays the entrance, the same id does not. */
  id: string;
  /** Accessible name of the page-tab group ("Team sections"). */
  label: string;
  tabs: PillContextTab[];
  activeKey: string;
  onSelect: (key: string) => void;
  primary?: PillContextAction;
};

/** At most this many page tabs fit one row next to the two icon buttons and the primary chip. */
export const PILL_MAX_TABS = 5;

/** The context the pill may render: tabs capped, unnamed ones dropped, a context with nothing to show is null. */
export function normalizePillContext(ctx: PillContext | null | undefined): PillContext | null {
  if (!ctx) return null;
  const tabs = ctx.tabs.filter((t) => t.key && t.label).slice(0, PILL_MAX_TABS);
  if (tabs.length === 0 && !ctx.primary) return null;
  const activeKey = tabs.some((t) => t.key === ctx.activeKey) ? ctx.activeKey : (tabs[0]?.key ?? "");
  return { ...ctx, tabs, activeKey };
}

export type PillMode = "global" | "context" | "menu";

/** global: the full tab row (no page context). context: two icons + the page segment. menu: the page segment folded away, the full tab row fanned out. */
export function pillMode(hasContext: boolean, menuOpen: boolean): PillMode {
  if (!hasContext) return "global";
  return menuOpen ? "menu" : "context";
}

/** Index of the lit page tab (for the sliding capsule); -1 when none. */
export function pillActiveIndex(ctx: Pick<PillContext, "tabs" | "activeKey">): number {
  return ctx.tabs.findIndex((t) => t.key === ctx.activeKey);
}

/** The label a pill tab shows: the short form where one is defined ("Hist."), else the label. The accessible name stays the full label. */
export function pillTabText(t: Pick<PillContextTab, "label" | "short">): string {
  return t.short || t.label;
}

/** Side margin kept clear of the fade when a scrolled tab is brought into view. */
export const PILL_SCROLL_MARGIN = 18;

/**
 * Where to scroll the page-tab strip so the lit tab is fully visible (clear of the edge fades), moving as little as
 * possible. Returns the new scrollLeft, clamped to the content.
 */
export function pillScrollTarget(tabX: number, tabW: number, viewW: number, scrollX: number, contentW: number): number {
  const max = Math.max(0, contentW - viewW);
  const m = Math.min(PILL_SCROLL_MARGIN, Math.max(0, (viewW - tabW) / 2));
  let next = scrollX;
  if (tabX - m < scrollX) next = tabX - m;
  else if (tabX + tabW + m > scrollX + viewW) next = tabX + tabW + m - viewW;
  return Math.max(0, Math.min(max, Math.round(next)));
}

/** Rough width of a bold 11-12px label: estimate used only to decide the primary chip's form before anything is measured. */
export function pillTextWidth(text: string): number {
  return Math.ceil(text.length * 6.6);
}
/** Width of the primary chip as a text chip (label + glyph + padding) and as the icon-only button. */
export const PILL_CHIP_ICON_W = 44;
export function pillChipTextWidth(label: string, hasGlyph: boolean): number {
  return pillTextWidth(label) + 28 + (hasGlyph ? 21 : 0) + 4;
}

/**
 * Whether the primary chip must collapse to the icon-only 40px button so no tab label is covered. It does when there
 * are four or more tabs, or when the tabs plus a text chip would not fit the width the segment has (`segmentW`: the row
 * minus the icon buttons and divider). A chip with no glyph has no icon form and stays text.
 */
export function pillPrimaryCompact(ctx: Pick<PillContext, "tabs" | "primary">, segmentW: number): boolean {
  const p = ctx.primary;
  if (!p || !p.glyph) return false;
  // The selection submit ("3 selected · Find trades") always reads as text: the page tabs step aside for it instead.
  if (p.key === SELECTION_ACTION_KEY) return false;
  if (ctx.tabs.length >= 4) return true;
  const tabsW = ctx.tabs.reduce((n, t) => n + pillTextWidth(pillTabText(t)) + 16, 0) + Math.max(0, ctx.tabs.length - 1) * 2;
  return tabsW + pillChipTextWidth(p.label, true) > segmentW;
}

// ---- One orb, smart footer (2026-11-14, coridian_: "the orb and the ellipsis just needs to be the orb") ----

/** Accessible name of the shell pill's orb (it unfolds the section row and More). The Fantasy Sim orb names its page instead (simOrbAriaLabel). */
export const PILL_ORB_LABEL = "Menu";

/** The shell orb's count badge: new items across the global tabs (trade offers), so folding the tab row away never hides them. */
export function pillOrbBadge(tabs: Pick<BottomTab, "badge">[]): number {
  return tabs.reduce((n, t) => n + (t.badge && t.badge > 0 ? Math.floor(t.badge) : 0), 0);
}

/** What the Fantasy Sim footer shows right now. The orb is always there and is the only navigation control (it opens the page menu). */
export type SimPillPlan = {
  /** Page tabs replace the action row (the draft room): orb + tabs + its one primary. null = the action row. */
  segment: PillContext | null;
  /** A page action that joins the row before Advance (Team: Auto-set). null = none. */
  inlineAction: PillContextAction | null;
  /** The compact "Sim to" button. Folded away when a page action takes its slot, in a draft, in the offseason and when paywalled; the orb menu still lists it. */
  simTo: boolean;
  /** The primary advance / stage button. Hidden while a tabbed segment owns the pill (a draft has no Advance). */
  advance: boolean;
};

/**
 * The smart rules for the Fantasy Sim footer, in one place (docs/ui-patterns.md "Smart footer rules"):
 *   tabbed page context (draft)      -> orb | tabs | primary            (no Advance, no Sim to)
 *   page action only (Team)          -> orb | page action | Advance     (Sim to moves into the orb menu)
 *   plain in-season page             -> orb | Sim to | Advance
 *   offseason / paywalled            -> orb | the stage button / Go Pro (no Sim to)
 * A page action that is disabled and not busy does not apply, so it is hidden rather than shown dead.
 */
export function simPillPlan(opts: { context: PillContext | null | undefined; simToAvailable: boolean; paywalled?: boolean }): SimPillPlan {
  const ctx = normalizePillContext(opts.context);
  if (ctx && ctx.tabs.length > 0) return { segment: ctx, inlineAction: null, simTo: false, advance: false };
  const p = ctx?.primary;
  const inlineAction = p && (!p.disabled || p.busy) ? p : null;
  return { segment: null, inlineAction, simTo: opts.simToAvailable && !opts.paywalled && !inlineAction, advance: true };
}

// ---- Sim footer, concept A (2026-11-18, owner pick): orb + page tabs + ONE primary chip ----

/** A chip longer than this (characters) cannot sit next to four text tabs at 390px: the strip yields a tab. */
export const SIM_CHIP_SHORT_MAX = 13;

/**
 * The Fantasy Sim page tabs the pill carries next to the primary chip. In season: Home / Team / Players / Trades (League and
 * More are one orb tap away, the trade count rides on the orb badge); a long chip ("⚠ 1 · Set lineup") takes the room of one
 * tab. The offseason has no Players tab and its stage chips are always long ("Start rookie draft", "Start S2 2027"), so it
 * carries Offseason / Team (Trades and League via the orb). Labels never clip: tabs yield instead of scrolling behind the chip.
 */
export function simFooterTabs(opts: { offseason?: boolean; chipLabel: string }): PillContextTab[] {
  if (opts.offseason) {
    return [
      { key: "home", label: "Offseason", glyph: "home" },
      { key: "team", label: "Team", glyph: "team" },
    ];
  }
  const all: PillContextTab[] = [
    { key: "home", label: "Home", glyph: "home" },
    { key: "team", label: "Team", glyph: "team" },
    { key: "players", label: "Players", glyph: "players" },
    { key: "trades", label: "Trades", glyph: "trades" },
  ];
  return opts.chipLabel.length > SIM_CHIP_SHORT_MAX ? all.slice(0, 3) : all;
}

/** The in-season primary chip: "Play Wk 6 ▸" ("Play round ▸" in the playoffs), or the amber "⚠ 1 · Set lineup" when starters will score 0. */
export function simAdvanceChip(opts: { phase?: string; week: number; issues: number }): { label: string; warn: boolean } {
  if (opts.issues > 0) return { label: `\u26A0\uFE0E ${opts.issues} \u00B7 Set lineup`, warn: true };
  return { label: opts.phase === "playoffs" ? "Play round \u25B8" : `Play Wk ${opts.week} \u25B8`, warn: false };
}

// ---- Selection mode, hide on scroll, reselect to top (2026-11-17, owner-approved smart footer upgrade) ----

/** Key of the primary action while a list has a selection (the footer's "3 selected · Find trades"). */
export const SELECTION_ACTION_KEY = "selection";

/** "3 selected · Find trades": the count the person built, then what the button does. */
export function selectionActionLabel(count: number, verb: string): string {
  return `${Math.max(0, Math.floor(count))} selected · ${verb}`;
}

/**
 * The footer's primary action for a pick-from-a-list + submit screen. With a selection it IS the submit button (enabled,
 * busy while submitting); with none it reverts to `fallback` (the page's usual primary, or nothing). One footer, never a
 * second sticky bar (docs/ui-patterns.md "Smart footer rules", scripts/check_selection_submit.mjs).
 */
export function selectionPrimary(opts: {
  count: number;
  verb: string;
  onPress: () => void;
  glyph?: TabIconName;
  busy?: boolean;
  disabled?: boolean;
  fallback?: PillContextAction;
}): PillContextAction | undefined {
  if (!(opts.count > 0)) return opts.fallback;
  return { key: SELECTION_ACTION_KEY, label: selectionActionLabel(opts.count, opts.verb), glyph: opts.glyph, busy: opts.busy, disabled: opts.disabled, onPress: opts.onPress };
}

/** True while the primary is the selection action: the footer stays visible then (hide-on-scroll pauses). */
export function isSelectionAction(p: Pick<PillContextAction, "key"> | null | undefined): boolean {
  return p?.key === SELECTION_ACTION_KEY;
}

/** Scroll distance (px) in one direction before the footer reacts, so a jitter or a small flick never toggles it. */
export const FOOTER_HIDE_THRESHOLD_PX = 12;
/** Within this distance of the top the footer is always shown. */
export const FOOTER_ALWAYS_SHOW_TOP_PX = 48;

/**
 * Hide-on-scroll state machine. Down past the threshold hides, up past the threshold shows, near the top always shows,
 * and `pinned` (a selection exists, the menu is open) keeps it shown. `anchorY` is the scroll offset where the current
 * direction started; the caller stores the returned `anchorY` and `hidden` and feeds them back with the next `y`.
 */
export function nextFooterScroll(
  prev: { hidden: boolean; lastY: number; anchorY: number; dir?: number },
  y: number,
  pinned: boolean,
): { hidden: boolean; lastY: number; anchorY: number; dir: number } {
  if (pinned || y <= FOOTER_ALWAYS_SHOW_TOP_PX) return { hidden: false, lastY: y, anchorY: y, dir: 0 };
  const dir = y > prev.lastY ? 1 : y < prev.lastY ? -1 : (prev.dir ?? 0);
  if (dir === 0) return { ...prev, lastY: y, dir };
  // A turn restarts the measure from where it turned, so only a real run in one direction crosses the threshold.
  const anchorY = dir === (prev.dir ?? 0) ? prev.anchorY : prev.lastY;
  const moved = y - anchorY;
  const hidden = moved >= FOOTER_HIDE_THRESHOLD_PX ? true : moved <= -FOOTER_HIDE_THRESHOLD_PX ? false : prev.hidden;
  return { hidden, lastY: y, anchorY, dir };
}

/** Footer tab long-press shortcut (app only; web tabs are links and iOS long-press on a link opens the preview sheet). */
export type TabShortcut = { label: string; onPress: () => void };

/** Sources of the More tab's count (waiver results, new roster injuries, Sim week ready). Each is a count the owning page already loaded. */
export type MoreBadgeSources = { waiverResults?: number; rosterInjuries?: number; simWeekReady?: number };

/** The More count: the sum of the sources (a source that is 0, missing or not a number adds nothing). */
export function moreBadgeTotal(src: MoreBadgeSources): number {
  return [src.waiverResults, src.rosterInjuries, src.simWeekReady].reduce<number>((n, v) => n + (v && v > 0 && Number.isFinite(v) ? Math.floor(v) : 0), 0);
}

/** Spoken breakdown for the More badge ("2 waiver results, 1 injury"), so the number is never unexplained. */
export function moreBadgeSummary(src: MoreBadgeSources): string {
  const parts: string[] = [];
  const w = Math.floor(src.waiverResults ?? 0);
  const i = Math.floor(src.rosterInjuries ?? 0);
  const s = Math.floor(src.simWeekReady ?? 0);
  if (w > 0) parts.push(`${w} waiver result${w === 1 ? "" : "s"}`);
  if (i > 0) parts.push(`${i} new injur${i === 1 ? "y" : "ies"}`);
  if (s > 0) parts.push("Sim week ready");
  return parts.join(", ");
}
