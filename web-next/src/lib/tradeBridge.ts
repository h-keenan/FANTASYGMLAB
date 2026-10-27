/**
 * Bridge from the public Trade Analyzer (/trade-analyzer, ?a=&b=) to a
 * signed-in account. A visitor builds a trade on neutral public values, taps
 * "See how this trade affects MY team", signs up and connects a league; this
 * module carries the entered trade through that flow and applies it to the
 * logged-in analyzer, where the roster-aware verdict can actually run.
 *
 * Only player ids travel (the same ones already in the shared URL); nothing
 * here is a value, a verdict or an account field. Storage is localStorage
 * with a short TTL, wrapped in try/catch: when it is unavailable the visitor
 * simply lands on the normal league home, never an error.
 *
 * The public ids are Sleeper player ids, the same ids the logged-in analyzer
 * keys its rankings and rosters on, so no mapping step is needed.
 */
import type { RankedPlayer } from "@/lib/api";
import { leagueHomePath } from "@/lib/leaguePlatform";
import { buildTradeSearch, parseTradeUrl } from "@/lib/seo/tradeAnalyzer";

const BRIDGE_KEY = "fd_pending_bridge_trade_v1";
const BRIDGE_TTL_MS = 24 * 60 * 60 * 1000;

export interface BridgeTrade {
  /** Players the visitor would send. */
  a: string[];
  /** Players the visitor would get. */
  b: string[];
}

/** Validated, de-duplicated ids (same rules as the shared-link parser), or null when a side is empty. */
export function sanitizeBridgeTrade(trade: { a?: readonly string[]; b?: readonly string[] } | null | undefined): BridgeTrade | null {
  if (!trade) return null;
  const parsed = parseTradeUrl(
    buildTradeSearch({ a: [...(trade.a ?? [])], b: [...(trade.b ?? [])], settings: { format: "1qb", tep: false } }),
  );
  return parsed.a.length > 0 && parsed.b.length > 0 ? { a: parsed.a, b: parsed.b } : null;
}

/** ?a=&b= from a query string, or null when it is not a complete trade. */
export function bridgeTradeFromSearch(search: string): BridgeTrade | null {
  const parsed = parseTradeUrl(search);
  return sanitizeBridgeTrade(parsed);
}

export function storePendingBridge(storage: Pick<Storage, "setItem"> | null | undefined, trade: BridgeTrade, now = Date.now()): void {
  const clean = sanitizeBridgeTrade(trade);
  if (!storage || !clean) return;
  try {
    storage.setItem(BRIDGE_KEY, JSON.stringify({ ...clean, at: now }));
  } catch {
    /* storage unavailable: the visitor just lands on the league home */
  }
}

export function readPendingBridge(storage: Pick<Storage, "getItem"> | null | undefined, now = Date.now()): BridgeTrade | null {
  if (!storage) return null;
  try {
    const raw = storage.getItem(BRIDGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { a?: string[]; b?: string[]; at?: number };
    if (typeof parsed.at !== "number" || now < parsed.at || now - parsed.at > BRIDGE_TTL_MS) return null;
    return sanitizeBridgeTrade(parsed);
  } catch {
    return null;
  }
}

export function clearPendingBridge(storage: Pick<Storage, "removeItem"> | null | undefined): void {
  try {
    storage?.removeItem(BRIDGE_KEY);
  } catch {
    /* ignore */
  }
}

function safeLocalStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function storePendingBridgeTrade(trade: BridgeTrade): void {
  storePendingBridge(safeLocalStorage(), trade);
}

/** Read once and always clear, so a stale trade never replays into a later session. */
export function consumePendingBridge(): BridgeTrade | null {
  const storage = safeLocalStorage();
  const trade = readPendingBridge(storage);
  clearPendingBridge(storage);
  return trade;
}

/** Logged-in analyzer URL for a league, carrying the entered trade. */
export function analyzerBridgePath(leagueId: string, leagueName: string, trade: BridgeTrade): string {
  const params = new URLSearchParams({ name: leagueName, a: trade.a.join(","), b: trade.b.join(",") });
  return `/trade-analyzer/${encodeURIComponent(leagueId)}?${params.toString().replace(/%2C/g, ",")}`;
}

/** League picker page for a returning user with several leagues. */
export function bridgePickerPath(trade: BridgeTrade): string {
  return `/trade-analyzer/bridge?a=${trade.a.join(",")}&b=${trade.b.join(",")}`;
}

/** Where a visitor goes after choosing/connecting a league: their pending
 * trade in that league's analyzer when there is one, else the league home. */
export function pathAfterLeagueChosen(leagueId: string, leagueName: string): string {
  const trade = consumePendingBridge();
  return trade ? analyzerBridgePath(leagueId, leagueName, trade) : leagueHomePath(leagueId, leagueName);
}

// ------------------------------------------------------------- applying

export interface BridgeTeam {
  rosterId: string;
  playerIds: ReadonlySet<string>;
}

export interface BridgeSkip {
  /** Player name when the league's pool has this id, else null. */
  name: string | null;
  reason: "not_in_league" | "not_on_your_roster" | "already_yours" | "not_on_a_roster" | "other_team";
}

export interface BridgeResolution {
  send: RankedPlayer[];
  receive: RankedPlayer[];
  /** Roster whose players fill the receive side (the first one found), or null. */
  partnerRosterId: string | null;
  skipped: BridgeSkip[];
  requested: number;
}

/**
 * Applies an entered trade to one league. The send side can only hold the
 * user's own players and the receive side one partner's players (the same
 * rules the builder enforces), so ids that do not fit are reported instead
 * of silently dropped or forced in.
 */
export function resolveBridgeTrade(input: {
  trade: BridgeTrade;
  rankings: readonly RankedPlayer[];
  myRosterIds: ReadonlySet<string>;
  otherTeams: readonly BridgeTeam[];
}): BridgeResolution {
  const byId = new Map(input.rankings.map((p) => [p.player_id, p]));
  const send: RankedPlayer[] = [];
  const receive: RankedPlayer[] = [];
  const skipped: BridgeSkip[] = [];
  let partnerRosterId: string | null = null;

  for (const id of input.trade.a) {
    const player = byId.get(id);
    if (!player) skipped.push({ name: null, reason: "not_in_league" });
    else if (input.myRosterIds.has(id)) send.push(player);
    else skipped.push({ name: player.name ?? null, reason: "not_on_your_roster" });
  }
  for (const id of input.trade.b) {
    const player = byId.get(id);
    if (!player) {
      skipped.push({ name: null, reason: "not_in_league" });
      continue;
    }
    if (input.myRosterIds.has(id)) {
      skipped.push({ name: player.name ?? null, reason: "already_yours" });
      continue;
    }
    const owner = input.otherTeams.find((team) => team.playerIds.has(id));
    if (!owner) skipped.push({ name: player.name ?? null, reason: "not_on_a_roster" });
    else if (partnerRosterId !== null && owner.rosterId !== partnerRosterId) {
      skipped.push({ name: player.name ?? null, reason: "other_team" });
    } else {
      partnerRosterId = owner.rosterId;
      receive.push(player);
    }
  }
  return { send, receive, partnerRosterId, skipped, requested: input.trade.a.length + input.trade.b.length };
}

const SKIP_REASON_TEXT: Record<BridgeSkip["reason"], string> = {
  not_in_league: "not in this league's player pool",
  not_on_your_roster: "not on your roster",
  already_yours: "already on your roster",
  not_on_a_roster: "not on any roster in this league",
  other_team: "on a different team than the first player you get",
};

/** One honest line saying what carried over and what did not. */
export function bridgeNotice(resolution: BridgeResolution): string {
  const applied = resolution.send.length + resolution.receive.length;
  if (resolution.skipped.length === 0) {
    return `Your public trade is loaded (${applied} player${applied === 1 ? "" : "s"}). Analyze it to see how it affects your team.`;
  }
  const missed = resolution.skipped
    .map((skip) => `${skip.name ?? "A player"} (${SKIP_REASON_TEXT[skip.reason]})`)
    .join(", ");
  const lead =
    applied === 0
      ? "None of the players from your public trade fit this league."
      : `Loaded ${applied} of ${resolution.requested} players from your public trade.`;
  return `${lead} Not added: ${missed}. Pick the rest from your roster and theirs.`;
}
