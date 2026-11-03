/**
 * "Build an offer" helpers (twin of web-next/src/lib/tradeOffer.ts) — pure, so
 * the node test runner covers them without rendering a screen.
 *
 * Quick View / Player Detail show one "Build an offer" button for a player on
 * ANOTHER team (never your own, never a free agent: those go to Waivers). The
 * TradeOffer screen asks GET .../trade-target for 2-3 built packages and each
 * card opens in Trade Analyzer ("Make a Trade") through `Trades.offerPrefill`,
 * which carries ids only; the Analyzer regrades the package itself.
 */

export interface OfferAsset {
  kind: 'player' | 'pick';
  id: string;
}

export interface OfferPrefill {
  send: string[];
  receive: string[];
  sendPicks: string[];
  receivePicks: string[];
}

export function canBuildOffer(
  playerId: string | null | undefined,
  ownership: { myPlayerIds: Set<string>; rosteredPlayerIds: Set<string> } | null,
): boolean {
  const id = String(playerId ?? '');
  if (!id || !ownership) return false;
  return ownership.rosteredPlayerIds.has(id) && !ownership.myPlayerIds.has(id);
}

const idsOf = (assets: OfferAsset[], kind: OfferAsset['kind']) =>
  assets.filter((a) => a.kind === kind && a.id).map((a) => a.id);

export function offerPrefillFrom(offer: { send: OfferAsset[]; receive: OfferAsset[] }): OfferPrefill {
  return {
    send: idsOf(offer.send, 'player'),
    receive: idsOf(offer.receive, 'player'),
    sendPicks: idsOf(offer.send, 'pick'),
    receivePicks: idsOf(offer.receive, 'pick'),
  };
}

/** Stable key so the Analyzer applies a given prefill once. */
export function offerPrefillKey(prefill: OfferPrefill): string {
  return [prefill.send, prefill.receive, prefill.sendPicks, prefill.receivePicks].map((l) => l.join(',')).join('|');
}

/** Resolve prefill ids against the league's pools, dropping any that are not
 * there (never invented). */
export function resolvePrefill<P extends { player_id: string }, K extends { pick_id: string }>(
  prefill: OfferPrefill,
  players: P[],
  picks: K[],
): { send: P[]; receive: P[]; sendPicks: K[]; receivePicks: K[] } {
  const playerById = new Map(players.map((p) => [p.player_id, p]));
  const pickById = new Map(picks.map((p) => [p.pick_id, p]));
  const pickPlayers = (ids: string[]) => ids.map((id) => playerById.get(id)).filter((p): p is P => Boolean(p));
  const pickPicks = (ids: string[]) => ids.map((id) => pickById.get(id)).filter((p): p is K => Boolean(p));
  return {
    send: pickPlayers(prefill.send),
    receive: pickPlayers(prefill.receive),
    sendPicks: pickPicks(prefill.sendPicks),
    receivePicks: pickPicks(prefill.receivePicks),
  };
}
