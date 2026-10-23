import type {
  DraftPicksResponse,
  LeagueRankingsResponse,
  LeagueTeamProfilesResponse,
  PortfolioLeagueResponse,
  RankedPlayer,
  TradeAnalyzerResponse,
} from "@/lib/api";
import { MAX_BODY_BYTES, buildAnalyzerIdea, buildPartnerPitch, parseAnalyzerPayload, rateLimited } from "@/lib/shareCard/analyzerShare";
import {
  UpstreamError,
  cacheKey,
  fetchUpstreamJson,
  getCachedPng,
  jsonError,
  parseShareFormat,
  pngResponse,
  putCachedPng,
  renderTradeCardPng,
} from "@/lib/shareCard/server";
import { analyzeFailureMessage } from "@/lib/tradeAnalyzerPresentation";

const RANKINGS_LIMIT = 300;

/**
 * POST /share-card/analyzer — the branded PNG for an ad-hoc Trade Analyzer
 * trade (no server-side id exists for one). The body names only the picked
 * assets; the verdict is re-run through the caller's own
 * POST .../trade-analyzer and every asset (name, value, tier, rating, pick
 * label) is resolved from their own rankings / draft-picks responses, so a
 * client can't put a made-up grade or value on the card. An id that can't be
 * resolved is a 404, never a partial card.
 */
export async function POST(request: Request): Promise<Response> {
  const authorization = request.headers.get("authorization") || "";
  if (!/^Bearer \S+$/.test(authorization)) return jsonError(401, "Not signed in.");

  if (Number(request.headers.get("content-length") || 0) > MAX_BODY_BYTES) return jsonError(413, "Request too large.");
  let text: string;
  try {
    text = await request.text();
  } catch {
    return jsonError(400, "Invalid request.");
  }
  if (text.length > MAX_BODY_BYTES) return jsonError(413, "Request too large.");
  let body: unknown;
  try {
    body = JSON.parse(text);
  } catch {
    return jsonError(400, "Invalid request.");
  }
  const parsed = parseAnalyzerPayload(body);
  if (!parsed.ok) return jsonError(422, parsed.detail);
  const payload = parsed.payload;
  const format = parseShareFormat(new URL(request.url).searchParams.get("format"));

  if (rateLimited(cacheKey([authorization]))) return jsonError(429, "Too many share cards. Try again in a minute.");

  const key = cacheKey(["analyzer", authorization, payload, format]);
  const cached = getCachedPng(key);
  if (cached) return pngResponse(cached, "hit");

  const league = `/v1/leagues/${encodeURIComponent(payload.leagueId)}`;
  const lensQ = `lens=${encodeURIComponent(payload.lens)}`;
  const playerIds = [...payload.sendPlayerIds, ...payload.receivePlayerIds];
  const pickIds = [...payload.sendPickIds, ...payload.receivePickIds];

  try {
    const [analysis, rankings, picks, profiles, mine] = await Promise.all([
      fetchUpstreamJson<TradeAnalyzerResponse>(`${league}/trade-analyzer`, authorization, {
        method: "POST",
        shareCardToken: true,
        jsonBody: {
          send_player_ids: payload.sendPlayerIds,
          receive_player_ids: payload.receivePlayerIds,
          send_pick_ids: payload.sendPickIds,
          receive_pick_ids: payload.receivePickIds,
          strategy: payload.strategy,
          lens: payload.lens,
          partner_roster_id: payload.partnerRosterId,
        },
      }),
      playerIds.length
        ? fetchUpstreamJson<LeagueRankingsResponse>(`${league}/rankings?${lensQ}&limit=${RANKINGS_LIMIT}`, authorization)
        : Promise.resolve<LeagueRankingsResponse>({ ok: true, players: [] }),
      pickIds.length ? fetchUpstreamJson<DraftPicksResponse>(`${league}/draft-picks?${lensQ}`, authorization) : Promise.resolve(null),
      payload.partnerRosterId
        ? fetchUpstreamJson<LeagueTeamProfilesResponse>(`${league}/team-profiles`, authorization).catch(() => null)
        : Promise.resolve(null),
      // Decorative and Premium-gated: fail open to "Your team".
      fetchUpstreamJson<PortfolioLeagueResponse>(
        `/v1/portfolio/leagues/${encodeURIComponent(payload.leagueId)}?${lensQ}`,
        authorization,
      ).catch(() => null),
    ]);

    if (!analysis.verdict) return jsonError(422, analyzeFailureMessage(analysis.reason || ""));

    const rankedById = new Map<string, RankedPlayer>((rankings.players ?? []).map((p) => [p.player_id, p]));
    // Players deeper than the rankings page: single-player lookup.
    await Promise.all(
      playerIds
        .filter((id) => !rankedById.has(id))
        .map(async (id) => {
          const one = await fetchUpstreamJson<{ player: RankedPlayer | null }>(
            `${league}/players/${encodeURIComponent(id)}/rank?${lensQ}`,
            authorization,
          ).catch(() => null);
          if (one?.player && one.player.player_id === id) rankedById.set(id, one.player);
        }),
    );
    const picksById = new Map((picks?.picks ?? []).map((p) => [p.pick_id, p]));

    const profile = payload.partnerRosterId ? profiles?.profiles?.[payload.partnerRosterId] : undefined;
    const idea = buildAnalyzerIdea(payload, {
      rankedById,
      picksById,
      verdict: analysis.verdict,
      partnerName: profile?.team_name || "",
      partnerAvatarUrl: profile?.avatar_url,
    });
    if (!idea) return jsonError(404, "Some of these players or picks are no longer available. Re-run the analysis.");

    const png = await renderTradeCardPng(idea, payload.lens, {
      format,
      myTeamName: mine?.league?.team_name,
      myAvatarUrl: mine?.league?.team_avatar_url,
      pitch: buildPartnerPitch(idea.package.send, idea.package.receive, profile?.team_name || ""),
    });
    putCachedPng(key, png);
    return pngResponse(png, "miss");
  } catch (error) {
    if (error instanceof UpstreamError) return jsonError(error.status, error.message);
    return jsonError(500, "Could not draw the share card.");
  }
}
