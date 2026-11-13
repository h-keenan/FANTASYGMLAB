import type { PortfolioIndexResponse, PortfolioLeagueResponse } from "@/lib/api";
import { PORTFOLIO_FRESH_MS } from "@/lib/portfolioLoader";
import type { PortfolioLeagueState } from "@/lib/portfolioProgress";

/**
 * Stale-while-revalidate for the web Portfolio (mobile gets the same behaviour
 * from its persisted React Query cache). The last COMPLETE Portfolio the person
 * saw is kept in localStorage, per user and lens, so a revisit paints every
 * league card instantly from it while the page revalidates in the background
 * (lib/portfolioLoader.ts `warm` / `skip`).
 *
 * Only finished rows are stored (never a headline-first row still waiting on
 * its signals, never a failure), each with its own timestamp. Best effort and
 * local only: private mode / disabled storage just means no instant paint.
 * Cleared on sign-out (AuthContext) so one person's leagues never survive into
 * the next sign-in on a shared browser.
 */

export const PORTFOLIO_SNAPSHOT_PREFIX = "fd:portfolio:v1:";
/** Older than this is not worth painting. */
export const PORTFOLIO_SNAPSHOT_MAX_AGE_MS = 24 * 60 * 60 * 1000;

export interface PortfolioSnapshotRow {
  at: number;
  data: PortfolioLeagueResponse;
}

export interface PortfolioSnapshot {
  index: PortfolioIndexResponse;
  rows: Record<string, PortfolioSnapshotRow>;
}

export function portfolioSnapshotKey(userId: string, lens: string): string {
  return `${PORTFOLIO_SNAPSHOT_PREFIX}${userId}:${lens}`;
}

function isRow(value: unknown): value is PortfolioSnapshotRow {
  const row = value as PortfolioSnapshotRow | null;
  return (
    typeof row?.at === "number" &&
    row.data != null &&
    typeof row.data === "object" &&
    row.data.league != null &&
    !row.data.signals_pending
  );
}

export function parsePortfolioSnapshot(raw: string | null | undefined, now: number): PortfolioSnapshot | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<PortfolioSnapshot> | null;
    const index = parsed?.index;
    if (!index || !index.is_premium || !Array.isArray(index.saved_leagues) || !parsed?.rows) return null;
    const rows: Record<string, PortfolioSnapshotRow> = {};
    for (const [leagueId, row] of Object.entries(parsed.rows)) {
      if (isRow(row) && now - row.at < PORTFOLIO_SNAPSHOT_MAX_AGE_MS) rows[leagueId] = row;
    }
    if (Object.keys(rows).length === 0) return null;
    return { index, rows };
  } catch {
    return null;
  }
}

/** What to persist for the current page state, or null when there is nothing worth keeping. */
export function buildPortfolioSnapshot(
  index: PortfolioIndexResponse | null,
  states: Record<string, PortfolioLeagueState | undefined>,
  updatedAt: Record<string, number>,
  previous: PortfolioSnapshot | null,
  now: number,
): PortfolioSnapshot | null {
  if (!index || !index.is_premium) return null;
  const rows: Record<string, PortfolioSnapshotRow> = {};
  for (const saved of index.saved_leagues ?? []) {
    const state = states[saved.league_id];
    if (state?.status === "success" && state.data.league && !state.data.signals_pending) {
      rows[saved.league_id] = { at: updatedAt[saved.league_id] ?? now, data: state.data };
    } else if (previous?.rows[saved.league_id]) {
      // Not (re)loaded this visit (below the fold, mid-revalidation): keep what we had.
      rows[saved.league_id] = previous.rows[saved.league_id];
    }
  }
  if (Object.keys(rows).length === 0) return null;
  return { index, rows };
}

/**
 * Starting states for the leagues the index lists: a league with a stored row
 * paints from it (`warm` = revalidate it, `skip` = younger than
 * PORTFOLIO_FRESH_MS so leave it alone); every other league starts pending.
 */
export function planFromSnapshot(
  snapshot: PortfolioSnapshot | null,
  leagueIds: string[],
  now: number,
): { states: Record<string, PortfolioLeagueState>; warm: string[]; skip: string[] } {
  const states: Record<string, PortfolioLeagueState> = {};
  const warm: string[] = [];
  const skip: string[] = [];
  for (const leagueId of leagueIds) {
    const row = snapshot?.rows[leagueId];
    if (row) {
      states[leagueId] = { status: "success", data: row.data };
      (now - row.at < PORTFOLIO_FRESH_MS ? skip : warm).push(leagueId);
    } else {
      states[leagueId] = { status: "pending" };
    }
  }
  return { states, warm, skip };
}

type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem" | "key" | "length">;

export function readPortfolioSnapshot(
  storage: StorageLike | null,
  userId: string,
  lens: string,
  now: number,
): PortfolioSnapshot | null {
  try {
    return parsePortfolioSnapshot(storage?.getItem(portfolioSnapshotKey(userId, lens)), now);
  } catch {
    return null;
  }
}

export function writePortfolioSnapshot(
  storage: StorageLike | null,
  userId: string,
  lens: string,
  snapshot: PortfolioSnapshot | null,
): void {
  try {
    const key = portfolioSnapshotKey(userId, lens);
    if (snapshot) storage?.setItem(key, JSON.stringify(snapshot));
    else storage?.removeItem(key);
  } catch {
    // quota / private mode: no instant paint next time, nothing else.
  }
}

export function clearPortfolioSnapshots(storage: StorageLike | null): void {
  try {
    if (!storage) return;
    const keys: string[] = [];
    for (let i = 0; i < storage.length; i += 1) {
      const key = storage.key(i);
      if (key?.startsWith(PORTFOLIO_SNAPSHOT_PREFIX)) keys.push(key);
    }
    for (const key of keys) storage.removeItem(key);
  } catch {
    // ignore
  }
}
