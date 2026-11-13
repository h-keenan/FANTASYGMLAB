import type { BottomTab } from "@/lib/bottomNav";
import { pathOwnsPhoneChrome } from "@/lib/bottomNav";
import { PAGE_TITLE_BY_SEGMENT } from "@/lib/navDestinations";

/**
 * Pure logic for the site-wide phone shell (Phase B of docs/mobile-ux-plan-2026-11.md):
 * the feature flag, the tab lists, route -> tab mapping and the standard
 * header's back target. Rendered by components/AppShellBar.tsx and
 * components/ShellHeader.tsx.
 */

export const SHELL_NAV_STORAGE_KEY = "fgl:nav";

/**
 * Rollout flag. Order of precedence:
 *  1. env NEXT_PUBLIC_BOTTOM_NAV=off is the kill switch: off for everyone, no override.
 *  2. ?nav=bottom turns it on, ?nav=off turns it off; either is remembered (localStorage "fgl:nav").
 *  3. a remembered choice.
 *  4. env NEXT_PUBLIC_BOTTOM_NAV=on turns it on for every signed-in user; otherwise ("founder", the default)
 *     it is on for the founder/owner account only.
 */
export function shellNavEnabled(opts: { env?: string | null; queryNav?: string | null; stored?: string | null; isFounder: boolean }): boolean {
  const env = (opts.env ?? "founder").toLowerCase();
  if (env === "off" || env === "0" || env === "false") return false;
  if (opts.queryNav === "bottom") return true;
  if (opts.queryNav === "off") return false;
  if (opts.stored === "bottom") return true;
  if (opts.stored === "off") return false;
  if (env === "on" || env === "1" || env === "true") return true;
  return opts.isFounder;
}

/** Whether a query value should be remembered (only the two real choices). */
export function shellNavQueryToStore(queryNav: string | null | undefined): "bottom" | "off" | null {
  return queryNav === "bottom" || queryNav === "off" ? queryNav : null;
}

export type ShellContext = { leagueId: string | null; leagueName: string };

/** League context: Today / Team / Trades / League / More. Outside a league: Home / Portfolio / Fantasy Sim / News / More. */
export function shellTabs(ctx: ShellContext): BottomTab[] {
  if (ctx.leagueId) {
    const id = encodeURIComponent(ctx.leagueId);
    const q = `?name=${encodeURIComponent(ctx.leagueName || ctx.leagueId)}`;
    return [
      { key: "today", label: "Today", glyph: "home", href: `/dashboard/${id}${q}` },
      { key: "team", label: "Team", glyph: "team", href: `/my-team/${id}${q}` },
      { key: "trades", label: "Trades", glyph: "trades", href: `/trade-hub/${id}${q}` },
      { key: "league", label: "League", glyph: "league", href: `/league-rankings/${id}${q}` },
      { key: "more", label: "More", glyph: "more" },
    ];
  }
  return [
    { key: "home", label: "Home", glyph: "home", href: "/" },
    { key: "portfolio", label: "Portfolio", glyph: "overview", href: "/portfolio" },
    { key: "sim", label: "Fantasy Sim", glyph: "scores", href: "/gm-game" },
    { key: "news", label: "News", glyph: "news", href: "/news" },
    { key: "more", label: "More", glyph: "more" },
  ];
}

const LEAGUE_SEGMENT_TAB: Record<string, string> = {
  dashboard: "today",
  alerts: "today",
  "my-team": "team",
  matchup: "team",
  players: "team",
  waivers: "team",
  "gm-plan": "team",
  "fantasy-sim": "team",
  "gm-targets": "team",
  "team-situation": "team",
  "draft-center": "team",
  "live-draft": "team",
  "player-compare": "team",
  "college-scouting": "team",
  "trade-hub": "trades",
  "trade-finder": "trades",
  "trade-analyzer": "trades",
  "trade-offer": "trades",
  "trade-history": "trades",
  "league-rankings": "league",
  "league-recaps": "league",
  games: "league",
  commissioner: "league",
};

const OUTSIDE_SEGMENT_TAB: Record<string, string> = {
  portfolio: "portfolio",
  "gm-game": "sim",
  news: "news",
};

/** The lit tab for a path. Anything that is not a tab's own section lights More. */
export function shellActiveTab(pathname: string | null | undefined, inLeague: boolean): string {
  const segment = (pathname || "").split("/").filter(Boolean)[0] ?? "";
  if (inLeague) return LEAGUE_SEGMENT_TAB[segment] ?? "more";
  if (segment === "") return "home";
  return OUTSIDE_SEGMENT_TAB[segment] ?? "more";
}

/** Paths where the shell bar can render: signed in, not the onboarding "/" flow... except outside a league "/" is Home. */
export function shellBarVisible(opts: { enabled: boolean; signedIn: boolean; pathname: string | null | undefined }): boolean {
  if (!opts.enabled || !opts.signedIn) return false;
  const p = opts.pathname || "";
  if (pathOwnsPhoneChrome(p)) return false; // the game has its own header and orb
  if (p === "/") return false; // sign-in / onboarding / paywall / import flow
  return true;
}

const TAB_ROOT_SEGMENTS = new Set(["dashboard", "my-team", "trade-hub", "league-rankings", "portfolio", "news"]);
const PARENT_SEGMENT: Record<string, string> = {
  "trade-finder": "trade-hub",
  "trade-analyzer": "trade-hub",
  "trade-offer": "trade-hub",
  "fantasy-sim": "gm-plan",
  "player-compare": "players",
};

/** The standard header's back target: the parent page's name, so "Players" is said on a player page. Null on a tab root. */
export function shellParent(pathname: string | null | undefined, ctx: ShellContext): { label: string; href: string } | null {
  const segment = (pathname || "").split("/").filter(Boolean)[0] ?? "";
  if (!segment || TAB_ROOT_SEGMENTS.has(segment) || pathOwnsPhoneChrome(pathname)) return null;
  const q = ctx.leagueId ? `?name=${encodeURIComponent(ctx.leagueName || ctx.leagueId)}` : "";
  const id = ctx.leagueId ? encodeURIComponent(ctx.leagueId) : "";
  const parts = (pathname || "").split("/").filter(Boolean);
  if (segment === "players" && parts.length > 2 && ctx.leagueId) return { label: PAGE_TITLE_BY_SEGMENT.players ?? "Players", href: `/players/${id}${q}` };
  const parentSeg = PARENT_SEGMENT[segment];
  if (parentSeg && ctx.leagueId) {
    return { label: PAGE_TITLE_BY_SEGMENT[parentSeg] ?? "Back", href: `/${parentSeg}/${id}${q}` };
  }
  if (ctx.leagueId) return { label: PAGE_TITLE_BY_SEGMENT.dashboard ?? "Today", href: `/dashboard/${id}${q}` };
  return { label: "Home", href: "/" };
}

/** DOM id of the page-aware action strip slot that sits above the tab bar. */
export const SHELL_ACTION_SLOT_ID = "shell-action-slot";
