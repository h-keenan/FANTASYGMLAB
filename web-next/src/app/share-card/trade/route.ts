import type { TradeHubResponse } from "@/lib/api";
import {
  UpstreamError,
  cacheKey,
  fetchUpstreamJson,
  getCachedPng,
  isSafeId,
  jsonError,
  pngResponse,
  putCachedPng,
  renderTradeCardPng,
} from "@/lib/shareCard/server";
import { isValuationLens } from "@/lib/valuationLens";


/**
 * GET /share-card/trade?leagueId=&rec=&strategy=&lens= — the branded
 * 1080x1350 PNG for one Trade Hub idea, drawn by web-next itself from the
 * app's own design tokens (lib/shareCard).
 *
 * Same trust rule as the old Python share-card.png endpoint: the idea is
 * never taken from the client. The caller's own bearer token is passed to
 * GET .../trade-hub (whose search the API caches), and the card is drawn
 * only for an idea that response really contains, matched by
 * recommendation_id. A stale or unknown id is a 404, never a made-up card.
 */
export async function GET(request: Request): Promise<Response> {
  const authorization = request.headers.get("authorization") || "";
  if (!/^Bearer \S+$/.test(authorization)) return jsonError(401, "Not signed in.");

  const params = new URL(request.url).searchParams;
  const leagueId = params.get("leagueId");
  const recommendationId = params.get("rec");
  const strategy = params.get("strategy") || "retool";
  const lens = params.get("lens") || "Dynasty";
  if (!isSafeId(leagueId) || !isSafeId(recommendationId) || !isSafeId(strategy)) {
    return jsonError(422, "leagueId, rec and strategy are required.");
  }
  if (!isValuationLens(lens)) return jsonError(422, "Unknown lens.");

  // Keyed on the caller's token too: two users never share a cached card.
  const key = cacheKey(["trade", authorization, leagueId, recommendationId, strategy, lens]);
  const cached = getCachedPng(key);
  if (cached) return pngResponse(cached, "hit");

  let board: TradeHubResponse;
  try {
    board = await fetchUpstreamJson<TradeHubResponse>(
      `/v1/leagues/${encodeURIComponent(leagueId)}/trade-hub?strategy=${encodeURIComponent(strategy)}&lens=${encodeURIComponent(lens)}&ad_unlocks=0`,
      authorization,
    );
  } catch (error) {
    const status = error instanceof UpstreamError ? error.status : 502;
    return jsonError(status, error instanceof Error ? error.message : "Could not load this trade.");
  }

  const idea = (board.ideas ?? []).find((candidate) => candidate.recommendation_id === recommendationId);
  if (!idea) {
    return jsonError(404, "This recommendation has changed. Review the latest analysis before sharing.");
  }

  try {
    const png = await renderTradeCardPng(idea, lens);
    putCachedPng(key, png);
    return pngResponse(png, "miss");
  } catch {
    return jsonError(500, "Could not draw the share card.");
  }
}
