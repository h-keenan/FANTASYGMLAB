/**
 * The one-field connect flow (UI pass 3, sheet 1 topic 2 V1): a Sleeper username and one "Connect" button, an instant
 * league list with avatars and checkboxes, then optional steps. Secondary paths (ESPN / Fleaflicker / MFL, an account,
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

export type ConnectWayKey = "espn" | "fleaflicker" | "mfl" | "account" | "sample";

export interface ConnectWay {
  key: ConnectWayKey;
  label: string;
  blurb: string;
}

const WAYS: ConnectWay[] = [
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
