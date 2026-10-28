import { loadTradeBoard } from "@/lib/seo/tradeBoardServer";
import { parseTradeUrl } from "@/lib/seo/tradeAnalyzer";
import { buildPublicTradeCard } from "@/lib/seo/tradeShare";
import { cacheKey, getCachedPng, jsonError, putCachedPng, renderTradeCardPng } from "@/lib/shareCard/server";

/**
 * GET /share-card/public-trade?a=&b=&f=&tep= — the 1200x630 link-unfurl card
 * for a trade entered in the public Trade Analyzer, so each shared
 * /trade-analyzer?a=&b= link previews its own trade.
 *
 * Public by design and built ONLY from public values: the ids in the query
 * are looked up on the anonymous value board (the same one behind
 * /api/public-trade-values); no token, roster, league or account data is read
 * or drawn. Ids that are not on the board are dropped, and a side left empty
 * is a 404 rather than a made-up card. The drawing is the same share-card
 * renderer the in-app trade card uses.
 */
export async function GET(request: Request): Promise<Response> {
  const state = parseTradeUrl(new URL(request.url).search);
  if (state.a.length === 0 || state.b.length === 0) {
    return jsonError(422, "Both sides of the trade are required (a and b).");
  }

  const key = cacheKey(["public-trade", state.a.join(","), state.b.join(","), state.settings.format, state.settings.tep]);
  const cached = getCachedPng(key);
  if (cached) return pngResponse(cached, "hit");

  let card: ReturnType<typeof buildPublicTradeCard>;
  try {
    card = buildPublicTradeCard(state, await loadTradeBoard());
  } catch {
    return jsonError(503, "Player values are not available right now.");
  }
  if (!card) return jsonError(404, "Those players are not on the public board.");

  try {
    const png = await renderTradeCardPng(card.idea, "Dynasty", { format: "og", myTeamName: "You", pitch: card.pitch });
    putCachedPng(key, png);
    return pngResponse(png, "miss");
  } catch {
    return jsonError(500, "Could not draw the share card.");
  }
}

/** Public values only, so (unlike the signed-in cards) shared caches may hold it. */
function pngResponse(png: ArrayBuffer, cacheState: "hit" | "miss"): Response {
  return new Response(png, {
    headers: {
      "Content-Type": "image/png",
      "Cache-Control": "public, max-age=3600, s-maxage=86400, stale-while-revalidate=86400",
      "X-Share-Card-Cache": cacheState,
    },
  });
}
