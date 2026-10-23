import type { LeagueRankingsResponse } from "@/lib/api";
import {
  UpstreamError,
  cacheKey,
  fetchUpstreamJson,
  privacyMaskerFor,
  getCachedPng,
  isSafeId,
  jsonError,
  pngResponse,
  putCachedPng,
  parseShareFormat,
  renderPlayerCardPng,
} from "@/lib/shareCard/server";
import { isValuationLens } from "@/lib/valuationLens";

/** Same page size the Player Profile page asks GET .../rankings for, so
 * the card covers exactly the players that page can show. */
const RANKINGS_LIMIT = 300;

/**
 * GET /share-card/player?leagueId=&playerId=&lens= — the branded 1080x1350
 * player card PNG. The player row comes from the caller's own
 * GET .../rankings (their bearer token, passed through), the same row the
 * Player Profile page renders, so the card never shows a value or rank the
 * page wouldn't.
 */
export async function GET(request: Request): Promise<Response> {
  const authorization = request.headers.get("authorization") || "";
  // Privacy mode (X-Privacy-Mode header): mask names/avatars in upstream data
  // before the card is drawn; part of the cache key so cards never mix.
  const masker = privacyMaskerFor(request);
  const fetchJson = <T,>(path: string, auth: string, init: Parameters<typeof fetchUpstreamJson>[2] = {}) =>
    fetchUpstreamJson<T>(path, auth, { ...init, masker });
  if (!/^Bearer \S+$/.test(authorization)) return jsonError(401, "Not signed in.");

  const params = new URL(request.url).searchParams;
  const leagueId = params.get("leagueId");
  const playerId = params.get("playerId");
  const lens = params.get("lens") || "Dynasty";
  const format = parseShareFormat(params.get("format"));
  if (!isSafeId(leagueId) || !isSafeId(playerId)) return jsonError(422, "leagueId and playerId are required.");
  if (!isValuationLens(lens)) return jsonError(422, "Unknown lens.");

  const key = cacheKey(["player", masker ? "private" : "", authorization, leagueId, playerId, lens, format]);
  const cached = getCachedPng(key);
  if (cached) return pngResponse(cached, "hit");

  let rankings: LeagueRankingsResponse;
  try {
    rankings = await fetchJson<LeagueRankingsResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/rankings?lens=${encodeURIComponent(lens)}&limit=${RANKINGS_LIMIT}`,
      authorization,
    );
  } catch (error) {
    const status = error instanceof UpstreamError ? error.status : 502;
    return jsonError(status, error instanceof Error ? error.message : "Could not load this player.");
  }

  const player = (rankings.players ?? []).find((candidate) => candidate.player_id === playerId);
  if (!player) return jsonError(404, "That player isn't on the current rankings board for this league.");

  try {
    const png = await renderPlayerCardPng(player, lens, { format, usageTrend: player.usage_trend ?? null });
    putCachedPng(key, png);
    return pngResponse(png, "miss");
  } catch {
    return jsonError(500, "Could not draw the share card.");
  }
}
