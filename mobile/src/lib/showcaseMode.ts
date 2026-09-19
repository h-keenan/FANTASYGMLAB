/**
 * Showcase mode — a dev-only recording mode that swaps every real person's
 * identity out of the UI so App Store / ad footage can be captured from a
 * live account without exposing league members' usernames, team names, or
 * league names.
 *
 * Two halves:
 *   1. Availability — a hardcoded email allowlist (below). Only a signed-in
 *      account whose email is on that list ever sees the toggle in More.
 *   2. Masking — `maskShowcaseFields` rewrites a fixed set of identity
 *      field names in every payload to deterministic fakes.
 *      `authorizedRequest` in lib/api.ts applies it to every response it
 *      returns, so one flag covers the whole app; the two screens that read
 *      `saved_leagues` straight from Supabase (Home and the GM Orb league
 *      switcher) call it directly, since those bypass the API client.
 *
 * Deliberately NOT masked: player names, positions, NFL teams, scores,
 * values — all the football data is the point of the footage.
 */

/**
 * Dev/founder account emails allowed to use showcase mode. Emails are
 * compared case-insensitively after trimming. Keep this to accounts you
 * control: anyone signed in with a listed email can flip the toggle.
 */
export const SHOWCASE_MODE_EMAILS: string[] = ['keenanhf@outlook.com'];

/** True when the signed-in account may use showcase mode at all. */
export function isShowcaseModeAvailable(email: string | null | undefined): boolean {
  if (!email) return false;
  const normalized = email.trim().toLowerCase();
  if (!normalized) return false;
  return SHOWCASE_MODE_EMAILS.some((allowed) => allowed.trim().toLowerCase() === normalized);
}

/**
 * Module-level because the masking runs inside `api.ts`, a plain module with
 * no access to React context. `ShowcaseModeProvider` pushes the current
 * value here in an effect (via `api.setShowcaseModeEnabled`).
 */
let showcaseModeEnabled = false;

export function setShowcaseModeEnabled(enabled: boolean): void {
  showcaseModeEnabled = enabled;
}

export function isShowcaseModeEnabled(): boolean {
  return showcaseModeEnabled;
}

/** Fake pools. Small and fixed so footage reads as a believable league. */
const TEAM_NAMES = [
  'Team Alpha',
  'Team Bravo',
  'Team Charlie',
  'Team Delta',
  'Team Echo',
  'Team Foxtrot',
  'Team Golf',
  'Team Hotel',
  'Team India',
  'Team Juliet',
  'Team Kilo',
  'Team Lima',
];

const LEAGUE_NAMES = [
  'Dynasty League',
  'Keeper League',
  'The League',
  'Superflex Dynasty',
  'Redraft Classic',
  'The Money League',
];

const OWNER_NAMES = [
  'Manager1',
  'Manager2',
  'Manager3',
  'Manager4',
  'Manager5',
  'Manager6',
  'Manager7',
  'Manager8',
  'Manager9',
  'Manager10',
  'Manager11',
  'Manager12',
];

const USERNAMES = [
  'gm_alpha',
  'gm_bravo',
  'gm_charlie',
  'gm_delta',
  'gm_echo',
  'gm_foxtrot',
  'gm_golf',
  'gm_hotel',
  'gm_india',
  'gm_juliet',
  'gm_kilo',
  'gm_lima',
];

const EMAILS = ['demo1@example.com', 'demo2@example.com', 'demo3@example.com', 'demo4@example.com'];

type MaskPool = 'team' | 'league' | 'owner' | 'username' | 'email';

/**
 * The masked field names, grouped by which fake pool they draw from. Every
 * entry came from grepping the API response interfaces in `lib/api.ts` for
 * identity-carrying names; bare `name` / `full_name` / `first_name` /
 * `last_name` are deliberately absent because in this API they are always
 * *player* names (LineupPlayer, PlayerSummary, RankedPlayer, WaiverPlayer,
 * TradeOutcomeAssetSummary, RecapTradeAsset, InjuryImpactPlayer,
 * PresentationAsset). Keys are matched anywhere in the payload, including
 * inside the `Record<string, unknown>` blobs that forward raw Sleeper
 * objects (hence `display_name`, and `team_name` nested under `metadata`).
 */
const MASKED_FIELDS: Record<string, MaskPool> = {
  team_name: 'team',
  partner_team_name: 'team',
  owner_team_name: 'team',
  original_team_name: 'team',
  league_name: 'league',
  last_league_name: 'league',
  owner_name: 'owner',
  display_name: 'owner',
  username: 'username',
  owner_username: 'username',
  sleeper_username: 'username',
  email: 'email',
};

const POOLS: Record<MaskPool, string[]> = {
  team: TEAM_NAMES,
  league: LEAGUE_NAMES,
  owner: OWNER_NAMES,
  username: USERNAMES,
  email: EMAILS,
};

/** FNV-1a — cheap, stable, no dependency. Only used to pick a pool slot. */
function hashString(value: string): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

/**
 * Deterministic: the same real name always maps to the same fake one for
 * the whole recording session (and across restarts), so the team that shows
 * as "Team Bravo" on the dashboard is still "Team Bravo" in the trade hub.
 */
export function fakeValueFor(pool: MaskPool, realValue: string): string {
  const options = POOLS[pool];
  return options[hashString(realValue) % options.length];
}

/** Guards a pathological/cyclic payload; real responses nest far less. */
const MAX_DEPTH = 32;

function maskValue(value: unknown, depth: number): unknown {
  if (depth > MAX_DEPTH) return value;
  if (Array.isArray(value)) {
    return value.map((entry) => maskValue(entry, depth + 1));
  }
  if (value && typeof value === 'object') {
    const source = value as Record<string, unknown>;
    const next: Record<string, unknown> = {};
    for (const key of Object.keys(source)) {
      const child = source[key];
      const pool = MASKED_FIELDS[key];
      if (pool && typeof child === 'string' && child.length > 0) {
        next[key] = fakeValueFor(pool, child);
      } else {
        next[key] = maskValue(child, depth + 1);
      }
    }
    return next;
  }
  return value;
}

/**
 * Deep-clones `value` with every masked identity field replaced. A no-op
 * (same reference back) whenever showcase mode is off, so the normal path
 * pays nothing.
 */
export function maskShowcaseFields<T>(value: T): T {
  if (!showcaseModeEnabled) return value;
  return maskValue(value, 0) as T;
}

/** Masks a single display string that never came through a JSON payload
 * (the signed-in account's own email on Home, for instance). */
export function maskShowcaseText(pool: MaskPool, value: string | null | undefined): string | null | undefined {
  if (!showcaseModeEnabled || !value) return value;
  return fakeValueFor(pool, value);
}

/** The masked field names, for docs/review. */
export const SHOWCASE_MASKED_FIELD_NAMES = Object.keys(MASKED_FIELDS);
