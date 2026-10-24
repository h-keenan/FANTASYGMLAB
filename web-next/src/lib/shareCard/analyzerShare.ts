/**
 * Trade Analyzer share card: the data builder. The analysis is already on
 * screen, so the card is a pure template filled from it: no server call, no
 * quota use. These helpers turn the on-screen verdict + both sides' assets
 * into the TradeIdea shape the trade card draws, plus the partner-addressed
 * pitch lines (computed only from the displayed asset scores).
 */

import type { TradeAsset, TradeIdea, TradeVerdict } from "@/lib/api";
import type { TradePitch } from "@/lib/shareCard/tradeCard";

export interface AnalyzerCardInput {
  /** What the user sends (the partner receives these). */
  sendAssets: TradeAsset[];
  /** What the user gets. */
  receiveAssets: TradeAsset[];
  verdict: TradeVerdict;
  partnerName: string;
  partnerAvatarUrl?: string | null;
}

const sum = (assets: TradeAsset[]) => assets.reduce((total, asset) => total + (Number(asset.score) || 0), 0);

/** On-screen analysis -> the TradeIdea the trade card draws. */
export function buildAnalyzerIdea(input: AnalyzerCardInput): TradeIdea {
  const { verdict, sendAssets, receiveAssets } = input;
  return {
    partner_team_name: input.partnerName || "Trade partner",
    partner_team_avatar_url: input.partnerAvatarUrl ?? null,
    rationale: verdict.rationale || "",
    trade_gain: verdict.value_delta,
    confidence_label: verdict.confidence,
    market_realism_label: "",
    reasoning_tags: [],
    category: "",
    value_edge_band: verdict.band,
    impact_tag: "",
    landed_gm_target_player_ids: [],
    send_score: sum(sendAssets),
    receive_score: sum(receiveAssets),
    package: { send: sendAssets, receive: receiveAssets, value_edge: verdict.band, confidence: verdict.confidence },
  };
}

/** Partner-addressed pitch built only from the displayed assets (the same
 * values the Analyzer shows). `send` is what the sender gives, i.e. what the
 * PARTNER receives. Each line is a fact computed from those values; a line
 * that isn't supported is omitted, and when the raw values favor the sender
 * the card never claims otherwise (neutral headline, no value line). */
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
