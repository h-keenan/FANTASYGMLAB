/**
 * Trade Analyzer share card: payload validation and the server-side
 * re-derivation that turns it into the TradeIdea shape the existing trade
 * card draws. An ad-hoc analyzer trade has no server id, so the client posts
 * only WHAT it picked (player ids, pick ids, partner roster id, strategy,
 * lens). Names, positions, values and the verdict/grade are all re-derived
 * from the caller's own API session; nothing numeric or textual that the
 * client sends is ever drawn.
 */

import type { DraftPickAsset, RankedPlayer, TradeAsset, TradeIdea, TradeVerdict } from "@/lib/api";
import type { TradePitch } from "@/lib/shareCard/tradeCard";
import { pickToTradeAsset, playerToTradeAsset } from "@/lib/tradeAnalyzerPresentation";
import { isValuationLens } from "@/lib/valuationLens";

export const MAX_ASSETS_PER_SIDE = 10;
export const MAX_BODY_BYTES = 4096;

const SAFE_ID = /^[A-Za-z0-9_.:-]{1,64}$/;

export interface AnalyzerSharePayload {
  leagueId: string;
  sendPlayerIds: string[];
  receivePlayerIds: string[];
  sendPickIds: string[];
  receivePickIds: string[];
  partnerRosterId: string;
  strategy: string;
  lens: string;
}

function idList(value: unknown): string[] | null {
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value) || value.length > MAX_ASSETS_PER_SIDE) return null;
  const out: string[] = [];
  for (const item of value) {
    if (typeof item !== "string" || !SAFE_ID.test(item)) return null;
    if (!out.includes(item)) out.push(item);
  }
  return out;
}

/** Strict allow-list parse; anything unexpected is rejected, not coerced. */
export function parseAnalyzerPayload(body: unknown): { ok: true; payload: AnalyzerSharePayload } | { ok: false; detail: string } {
  if (!body || typeof body !== "object" || Array.isArray(body)) return { ok: false, detail: "Invalid trade." };
  const raw = body as Record<string, unknown>;
  const leagueId = raw.leagueId;
  if (typeof leagueId !== "string" || !SAFE_ID.test(leagueId)) return { ok: false, detail: "leagueId is required." };
  const sendPlayerIds = idList(raw.sendPlayerIds);
  const receivePlayerIds = idList(raw.receivePlayerIds);
  const sendPickIds = idList(raw.sendPickIds);
  const receivePickIds = idList(raw.receivePickIds);
  const tooMany = { ok: false as const, detail: `Each side takes at most ${MAX_ASSETS_PER_SIDE} valid assets.` };
  if (!sendPlayerIds || !receivePlayerIds || !sendPickIds || !receivePickIds) return tooMany;
  if (
    sendPlayerIds.length + sendPickIds.length > MAX_ASSETS_PER_SIDE ||
    receivePlayerIds.length + receivePickIds.length > MAX_ASSETS_PER_SIDE
  ) {
    return tooMany;
  }
  if (!sendPlayerIds.length && !receivePlayerIds.length && !sendPickIds.length && !receivePickIds.length) {
    return { ok: false, detail: "Add at least one asset to the trade." };
  }
  const partnerRosterId = raw.partnerRosterId === undefined || raw.partnerRosterId === null ? "" : raw.partnerRosterId;
  if (typeof partnerRosterId !== "string" || (partnerRosterId && !SAFE_ID.test(partnerRosterId))) {
    return { ok: false, detail: "Invalid trade partner." };
  }
  const strategy = raw.strategy === undefined ? "retool" : raw.strategy;
  if (typeof strategy !== "string" || !SAFE_ID.test(strategy)) return { ok: false, detail: "Invalid strategy." };
  const lens = raw.lens === undefined ? "Dynasty" : raw.lens;
  if (typeof lens !== "string" || !isValuationLens(lens)) return { ok: false, detail: "Unknown lens." };
  return {
    ok: true,
    payload: { leagueId, sendPlayerIds, receivePlayerIds, sendPickIds, receivePickIds, partnerRosterId, strategy, lens },
  };
}

/** Per-caller sliding-window limiter (in-process): the route fans out to
 * several upstream calls per draw. */
const hits = new Map<string, number[]>();
export function rateLimited(key: string, now = Date.now(), limit = 10, windowMs = 60_000): boolean {
  const recent = (hits.get(key) ?? []).filter((t) => now - t < windowMs);
  if (recent.length >= limit) {
    hits.set(key, recent);
    return true;
  }
  recent.push(now);
  if (hits.size > 500 && !hits.has(key)) hits.delete(hits.keys().next().value as string);
  hits.set(key, recent);
  return false;
}
export function clearRateLimitForTests() {
  hits.clear();
}

export interface AnalyzerResolved {
  rankedById: Map<string, RankedPlayer>;
  picksById: Map<string, DraftPickAsset>;
  verdict: TradeVerdict;
  partnerName: string;
  partnerAvatarUrl?: string | null;
}

function side(playerIds: string[], pickIds: string[], resolved: AnalyzerResolved): TradeAsset[] | null {
  const out: TradeAsset[] = [];
  for (const id of playerIds) {
    const player = resolved.rankedById.get(id);
    if (!player) return null;
    out.push(playerToTradeAsset(player));
  }
  for (const id of pickIds) {
    const pick = resolved.picksById.get(id);
    if (!pick) return null;
    out.push(pickToTradeAsset(pick));
  }
  return out;
}

const sum = (assets: TradeAsset[]) => assets.reduce((total, asset) => total + (Number(asset.score) || 0), 0);

/** Verdict + server-resolved assets -> the TradeIdea the trade card draws.
 * null when any posted id could not be resolved (never a partial card). */
export function buildAnalyzerIdea(payload: AnalyzerSharePayload, resolved: AnalyzerResolved): TradeIdea | null {
  const send = side(payload.sendPlayerIds, payload.sendPickIds, resolved);
  const receive = side(payload.receivePlayerIds, payload.receivePickIds, resolved);
  if (!send || !receive) return null;
  const { verdict } = resolved;
  return {
    partner_team_name: resolved.partnerName || "Trade partner",
    partner_team_avatar_url: resolved.partnerAvatarUrl ?? null,
    rationale: verdict.rationale || "",
    trade_gain: verdict.value_delta,
    confidence_label: verdict.confidence,
    market_realism_label: "",
    reasoning_tags: [],
    category: "",
    value_edge_band: verdict.band,
    impact_tag: "",
    landed_gm_target_player_ids: [],
    send_score: sum(send),
    receive_score: sum(receive),
    package: { send, receive, value_edge: verdict.band, confidence: verdict.confidence },
  };
}

/** Partner-addressed pitch built only from the resolved assets (the same
 * rankings/draft-picks values the Analyzer shows). `send` is what the sender
 * gives, i.e. what the PARTNER receives. Each line is a fact computed from
 * those values; a line that isn't supported is omitted, and when the raw
 * values favor the sender the card never claims otherwise (neutral headline,
 * no value line). */
export function buildPartnerPitch(send: TradeAsset[], receive: TradeAsset[], partnerName: string): TradePitch {
  const gets = sum(send);
  const gives = sum(receive);
  const net = gets - gives;
  const larger = Math.max(gets, gives);
  const fair = larger > 0 && Math.abs(net) <= larger * 0.05;
  const lines: string[] = [];

  if (net > 0 && !fair) lines.push(`You gain ${Math.round(net).toLocaleString("en-US")} in value`);
  else if (fair) lines.push("Fair value both ways");

  // Upgrade at a position: the best incoming player beats the best outgoing
  // player at the same position.
  const best = (assets: TradeAsset[]) => {
    const map = new Map<string, TradeAsset>();
    for (const a of assets) {
      if (a.asset_type === "pick" || !a.position) continue;
      const cur = map.get(a.position);
      if (!cur || (Number(a.score) || 0) > (Number(cur.score) || 0)) map.set(a.position, a);
    }
    return map;
  };
  const incoming = best(send);
  const outgoing = best(receive);
  let upgrade: { pos: string; gain: number; inName: string } | null = null;
  for (const [pos, inAsset] of incoming) {
    const out = outgoing.get(pos);
    if (!out) continue;
    const gain = (Number(inAsset.score) || 0) - (Number(out.score) || 0);
    if (gain > 0 && (!upgrade || gain > upgrade.gain)) upgrade = { pos, gain, inName: inAsset.name || "" };
  }
  if (upgrade && upgrade.inName) lines.push(`Upgrade at ${upgrade.pos}: ${upgrade.inName}`);

  const picksIn = send.filter((a) => a.asset_type === "pick");
  if (picksIn.length) {
    lines.push(picksIn.length === 1 ? `Adds a ${picksIn[0].season ?? ""} Round ${picksIn[0].round ?? ""} pick`.replace(/\s+/g, " ") : `Adds ${picksIn.length} draft picks`);
  }

  const name = partnerName.trim();
  const favorsPartner = net >= 0 || fair;
  const headline = name
    ? favorsPartner
      ? `A trade that works for ${name}`
      : `Trade proposal for ${name}`
    : "Trade proposal";
  return { headline, lines: lines.slice(0, 3) };
}
