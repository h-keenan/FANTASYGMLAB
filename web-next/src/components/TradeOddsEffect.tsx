"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, type TradeAsset, type TradeOddsEffectResponse } from "@/lib/api";
import { tradeOddsView, type WhatIfTone } from "@/lib/gamesPresentation";

/**
 * "Effect on your odds" row for a trade (Analyzer verdict, Trade Hub and Trade
 * Finder ideas). Fetched lazily from POST .../trade-odds-effect (the Season
 * Simulator re-run with the post-trade roster), so it never slows the verdict
 * itself. Shows nothing when there is nothing real to show (offseason, no games
 * left, simulator unavailable, request failed); Free accounts get a one-line
 * Premium pointer instead. Mirrors mobile's TradeOddsEffect.
 */

const cache = new Map<string, Promise<TradeOddsEffectResponse>>();

function fetchOnce(leagueId: string, send: string[], receive: string[], hasPicks: boolean, lens: string) {
  const key = JSON.stringify([leagueId, lens, [...send].sort(), [...receive].sort(), hasPicks]);
  let pending = cache.get(key);
  if (!pending) {
    pending = api.postTradeOddsEffect(
      leagueId,
      [{ send_player_ids: send, receive_player_ids: receive, has_picks: hasPicks }],
      lens,
    );
    cache.set(key, pending);
    pending.catch(() => cache.delete(key));
  }
  return pending;
}

const TONE_COLOR: Record<WhatIfTone, string> = {
  positive: "var(--color-success)",
  negative: "var(--color-danger)",
  neutral: "var(--color-text-secondary)",
};

export function splitTradeAssets(assets: TradeAsset[]): { ids: string[]; hasPicks: boolean } {
  const ids: string[] = [];
  let hasPicks = false;
  for (const asset of assets) {
    if (asset.asset_type === "pick") hasPicks = true;
    else if (asset.player_id) ids.push(asset.player_id);
  }
  return { ids, hasPicks };
}

export function TradeOddsEffect({
  leagueId,
  send,
  receive,
  lens = "Dynasty",
}: {
  leagueId: string;
  send: TradeAsset[];
  receive: TradeAsset[];
  lens?: string;
}) {
  const [response, setResponse] = useState<TradeOddsEffectResponse | null>(null);
  const sendSplit = splitTradeAssets(send);
  const receiveSplit = splitTradeAssets(receive);
  const sendKey = sendSplit.ids.join(",");
  const receiveKey = receiveSplit.ids.join(",");
  const hasPicks = sendSplit.hasPicks || receiveSplit.hasPicks;

  useEffect(() => {
    let cancelled = false;
    if (!sendKey && !receiveKey) return;
    fetchOnce(leagueId, sendKey ? sendKey.split(",") : [], receiveKey ? receiveKey.split(",") : [], hasPicks, lens)
      .then((result) => {
        if (!cancelled) setResponse(result);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [leagueId, sendKey, receiveKey, hasPicks, lens]);

  if (!response) return null;
  if (response.reason === "premium_required") {
    return (
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="trade-odds-upsell">
        {response.upsell?.title ?? "See how a trade moves your odds"}.{" "}
        <Link href="/premium" className="font-bold" style={{ color: "var(--color-premium)" }}>
          Premium →
        </Link>
      </p>
    );
  }
  const view = tradeOddsView(response.reason ? null : response.results[0]);
  if (!view) return null;
  return (
    <div className="flex flex-col gap-1" data-testid="trade-odds-effect">
      <span
        className="text-xs uppercase font-bold"
        style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
      >
        Effect on your odds
      </span>
      <p className="text-sm font-bold" style={{ color: TONE_COLOR[view.tone], fontVariantNumeric: "tabular-nums" }}>
        {view.headline}
      </p>
      {view.titleLine ? (
        <p className="text-sm" style={{ color: "var(--color-text-secondary)", fontVariantNumeric: "tabular-nums" }}>
          {view.titleLine}
        </p>
      ) : null}
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {view.detail}
        {view.notes.length ? `. ${view.notes.join(" ")}` : ""}
      </p>
    </div>
  );
}
