/**
 * "Build an offer" links, shared by the Quick View button, the offer result
 * cards and the Trade Analyzer prefill. Twin of mobile/src/lib/tradeOffer.ts.
 *
 * An offer travels to the Analyzer as plain ids (the same ids the Analyzer
 * already keys on): `send` / `receive` player ids and `sendPicks` /
 * `receivePicks` pick ids ("season:round:original_roster_id"). Nothing about
 * the offer's value or verdict travels; the Analyzer regrades it, so a tweaked
 * offer is always graded by the current Analyzer.
 */
import type { TradeTargetOffer } from "@/lib/api";

export interface OfferPrefill {
  send: string[];
  receive: string[];
  sendPicks: string[];
  receivePicks: string[];
}

const ids = (assets: TradeTargetOffer["send"], kind: "player" | "pick") =>
  assets.filter((a) => a.kind === kind && a.id).map((a) => a.id);

export function offerBuilderHref(leagueId: string, leagueName: string, playerId: string): string {
  const params = new URLSearchParams({ name: leagueName, playerId });
  return `/trade-offer/${encodeURIComponent(leagueId)}?${params.toString()}`;
}

export function offerAnalyzerHref(
  leagueId: string,
  leagueName: string,
  offer: Pick<TradeTargetOffer, "send" | "receive">,
): string {
  const params = new URLSearchParams({ name: leagueName });
  const set = (key: string, values: string[]) => {
    if (values.length > 0) params.set(key, values.join(","));
  };
  set("send", ids(offer.send, "player"));
  set("receive", ids(offer.receive, "player"));
  set("sendPicks", ids(offer.send, "pick"));
  set("receivePicks", ids(offer.receive, "pick"));
  return `/trade-analyzer/${encodeURIComponent(leagueId)}?${params.toString().replace(/%2C/g, ",").replace(/%3A/g, ":")}`;
}

/** The prefill carried by an Analyzer URL, or null when it is not an offer. */
export function offerPrefillFromSearch(search: { get(name: string): string | null }): OfferPrefill | null {
  const list = (key: string) =>
    (search.get(key) ?? "")
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean);
  const prefill = {
    send: list("send"),
    receive: list("receive"),
    sendPicks: list("sendPicks"),
    receivePicks: list("receivePicks"),
  };
  // An offer always brings something back.
  return prefill.receive.length + prefill.receivePicks.length > 0 ? prefill : null;
}

/**
 * Whether "Build an offer" belongs under a player in Quick View: only for a
 * player on ANOTHER roster in the league. Your own players are not targets and
 * a free agent is a Waivers move, not a trade.
 */
export function canBuildOffer(
  playerId: string | null | undefined,
  ownership: { myPlayerIds: Set<string>; rosteredPlayerIds: Set<string> } | null,
): boolean {
  const id = String(playerId ?? "");
  if (!id || !ownership) return false;
  return ownership.rosteredPlayerIds.has(id) && !ownership.myPlayerIds.has(id);
}
