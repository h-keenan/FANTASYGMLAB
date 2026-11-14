import type { TabIconName } from "@/lib/tabIcons";

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
  /** Route for tabs that navigate (the site shell); in-page tabs leave it off. */
  href?: string;
};

/** 44px is the smallest tap target the bar may render. */
export const BOTTOM_BAR_MIN_TARGET_PX = 44;

/** "" never shows; 1 to 9 as is; 10 and up as "9+" so the badge keeps its shape. */
export function bottomTabBadgeText(count: number | null | undefined): string | null {
  if (!count || count < 1 || !Number.isFinite(count)) return null;
  return count > 9 ? "9+" : String(Math.floor(count));
}

/** Accessible name: the label plus the count in words, so a badge is never icon-only. */
export function bottomTabAriaLabel(tab: Pick<BottomTab, "label" | "badge">): string {
  const text = bottomTabBadgeText(tab.badge);
  if (!text) return tab.label;
  const n = Math.floor(tab.badge ?? 0);
  return `${tab.label}, ${n} new`;
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
export function simStatusChips(pending: { lineup_warnings?: number; inbox?: number } | null | undefined): SimStatusChip[] {
  const out: SimStatusChip[] = [];
  const w = pending?.lineup_warnings ?? 0;
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
  // Starts with what the orb shows (the page name, then the badge): WCAG 2.5.3 Label in Name.
  const shown = n > 9 ? "9+" : String(n);
  return n > 0 ? `${currentLabel} ${shown}. Game menu, ${n} trade offer${n === 1 ? "" : "s"} waiting` : `${currentLabel}. Game menu`;
}
