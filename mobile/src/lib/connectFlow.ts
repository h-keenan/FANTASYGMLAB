/**
 * The one-field connect flow (UI pass 3, sheet 1 topic 2 V1): a Sleeper username and one "Connect" button, an instant
 * league list with avatars and checkboxes, then optional steps. Secondary paths (Yahoo / ESPN / Fleaflicker / MFL, an account,
 * the sample league) sit behind "More ways to connect". Pure and import-free; byte-identical twin of
 * mobile/src/lib/connectFlow.ts so web and the app never disagree on copy, defaults or what a save outcome means.
 */

export const CONNECT_PRIMARY_LABEL = "Connect";
export const CONNECT_FIELD_LABEL = "Sleeper username";
export const CONNECT_PLACEHOLDER = "e.g. gridiron_gm";
/** The one trust line (the longer explanation stays one tap away under "What is Sleeper?"). */
export const CONNECT_TRUST_LINE = "Read-only. We never ask for your Sleeper password or change your lineup.";
export const CONNECT_MORE_LABEL = "More ways to connect";
export const CONNECT_WHAT_IS_SLEEPER =
  "FantasyDesk connects to your existing Sleeper fantasy league: it reads your real roster, matchups and league settings to build recommendations. Sleeper is a free app and website for running a fantasy league.";

/** Where the username lives. Shown under "What is Sleeper?" (web) and under the trust line in the app's add-league sheet. */
export const CONNECT_FIND_USERNAME = "Find it in the Sleeper app: profile > your username, not your email.";

/** Up-front limit for a non-Sleeper platform. Same sentence the server sends as `platform_notice` on Today (services/mobile_api_service.py). */
export function connectPlatformNotice(platformLabel: string): string {
  return `Waiver and trade suggestions aren't available for ${platformLabel} leagues yet, so you'll only see what your imported roster can support.`;
}

export type ConnectWayKey = "yahoo" | "espn" | "fleaflicker" | "mfl" | "account" | "sample";

export interface ConnectWay {
  key: ConnectWayKey;
  label: string;
  blurb: string;
}

const WAYS: ConnectWay[] = [
  { key: "yahoo", label: "Yahoo", blurb: "Sign in with Yahoo, pick your league" },
  { key: "espn", label: "ESPN", blurb: "League ID. Private leagues need 2 cookies" },
  { key: "fleaflicker", label: "Fleaflicker", blurb: "League ID" },
  { key: "mfl", label: "MFL", blurb: "League ID" },
  { key: "account", label: "Sign in or create an account", blurb: "Email, Google or Apple. Your leagues follow you across devices" },
  { key: "sample", label: "Try the sample league", blurb: "No sign-up, 20 seconds" },
];

/** The compact secondary rows. `account` is hidden when already signed in with a real account. */
export function connectWays(opts: { hasAccount: boolean }): ConnectWay[] {
  return WAYS.filter((way) => !(way.key === "account" && opts.hasAccount));
}

export interface ConnectLeague {
  league_id: string;
  name: string;
  season: string;
  total_rosters: number;
  avatar_url?: string | null;
}

/** Newest season first (a rolled-over dynasty league has one id per season, so the year must be visible). */
export function groupLeaguesBySeason<T extends ConnectLeague>(leagues: ReadonlyArray<T>): { season: string; leagues: T[] }[] {
  const seasons = Array.from(new Set(leagues.map((l) => l.season))).sort((a, b) => Number(b) - Number(a));
  return seasons.map((season) => ({ season, leagues: leagues.filter((l) => l.season === season) }));
}

/** Preselect exactly one league: the first of the newest season, so one tap on Connect is enough. */
export function defaultLeagueSelection(leagues: ReadonlyArray<ConnectLeague>): string[] {
  const first = groupLeaguesBySeason(leagues)[0]?.leagues[0];
  return first ? [first.league_id] : [];
}

export function toggleLeague(selected: ReadonlyArray<string>, id: string): string[] {
  return selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id];
}

export function connectCtaLabel(count: number): string {
  if (count <= 0) return "Pick a league";
  return count === 1 ? "Connect 1 league" : `Connect ${count} leagues`;
}

export function leagueMeta(l: Pick<ConnectLeague, "season" | "total_rosters">): string {
  return [l.season, l.total_rosters ? `${l.total_rosters} teams` : ""].filter(Boolean).join(" · ");
}

/** Save order: newest season first, the first one becomes the default league. */
export function planSaves<T extends ConnectLeague>(selected: ReadonlyArray<string>, leagues: ReadonlyArray<T>): { league: T; makeDefault: boolean }[] {
  const picked = groupLeaguesBySeason(leagues.filter((l) => selected.includes(l.league_id))).flatMap((g) => g.leagues);
  return picked.map((league, i) => ({ league, makeDefault: i === 0 }));
}

export interface SaveOutcome {
  leagueId: string;
  leagueName: string;
  ok: boolean;
  /** Server reason on failure: "at_cap", "league_not_found", ... */
  reason?: string | null;
  warming?: boolean;
}

export interface SaveSummary {
  /** The league to open (the first that saved). */
  open: { leagueId: string; leagueName: string; warming: boolean } | null;
  savedCount: number;
  /** The plan's league cap stopped at least one save: show the Pro note, but never block the ones that saved. */
  atCap: boolean;
  /** Failures that are not the cap (the user is told, the rest still open). */
  failedReason: string | null;
}

export function summarizeSaves(outcomes: ReadonlyArray<SaveOutcome>): SaveSummary {
  const saved = outcomes.filter((o) => o.ok);
  const failed = outcomes.filter((o) => !o.ok);
  const first = saved[0];
  return {
    open: first ? { leagueId: first.leagueId, leagueName: first.leagueName, warming: Boolean(first.warming) } : null,
    savedCount: saved.length,
    atCap: failed.some((o) => o.reason === "at_cap"),
    failedReason: failed.find((o) => o.reason !== "at_cap")?.reason ?? null,
  };
}

export type ConnectMode = "connect" | "sample" | "sim";

/** The connect step's three ways in (segments/tabs on web and in the app). Sim needs no league. */
export const CONNECT_MODES: ReadonlyArray<{ key: ConnectMode; label: string; blurb: string; action: string }> = [
  { key: "connect", label: "Connect my league", blurb: "", action: "Connect" },
  { key: "sample", label: "Try a sample league", blurb: "Look around a ready-made league. No sign-up, 20 seconds.", action: "Try a sample league" },
  { key: "sim", label: "Play Fantasy Sim", blurb: "Draft a team and play a season against AI managers. No league needed. Your first season is free.", action: "Start a quick game" },
];

/** Web deep link into a Quick Fantasy Sim game (ads, onboarding). The app twin is fantasygmlab://gm-game?quickstart=1. */
export const SIM_QUICKSTART_PATH = "/gm-game?quickstart=1";
