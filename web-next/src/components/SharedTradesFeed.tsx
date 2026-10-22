"use client";

import { useState } from "react";

import { Button } from "@/components/Button";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { ToneBadge } from "@/components/ToneBadge";
import type { SharedCommunityTrade } from "@/lib/api";
import {
  formatCommunityTradeDate,
  sharedTradeGradeColor,
  toSharedTradeAssets,
} from "@/lib/communityTradesPresentation";

function SharedTradeCard({
  trade,
  onDelete,
  onReport,
}: {
  trade: SharedCommunityTrade;
  onDelete: (id: string) => void;
  onReport: (id: string) => void;
}) {
  const date = formatCommunityTradeDate(trade.created_at);
  const color = sharedTradeGradeColor(trade.grade);
  return (
    <article className="glass-surface flex flex-col gap-2 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col min-w-0">
          <h3 style={{ font: "var(--font-card-title)" }}>{trade.display_name}</h3>
          {date ? (
            <span className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
              {date}
            </span>
          ) : null}
        </div>
        <ToneBadge label={trade.band || trade.grade} color={color} />
      </div>
      {trade.why ? (
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {trade.why}
        </p>
      ) : null}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <ExchangeSide label="Sent" dotColor="var(--color-danger)" assets={toSharedTradeAssets(trade.send)} />
        <ExchangeSide label="Received" dotColor="var(--color-success)" assets={toSharedTradeAssets(trade.receive)} />
      </div>
      <div className="flex justify-end">
        {trade.mine ? (
          <Button variant="ghost" size="sm" onClick={() => onDelete(trade.id)}>
            Delete
          </Button>
        ) : (
          <Button variant="ghost" size="sm" onClick={() => onReport(trade.id)}>
            Report
          </Button>
        )}
      </div>
    </article>
  );
}

/**
 * Opt-in shared trades. Renders nothing when the feature is unavailable
 * (storage not set up) or there is nothing to show.
 */
export function SharedTradesFeed({
  available,
  trades,
  onDelete,
  onReport,
}: {
  available: boolean;
  trades: SharedCommunityTrade[];
  onDelete: (id: string) => void | Promise<unknown>;
  onReport: (id: string) => void | Promise<unknown>;
}) {
  const [reported, setReported] = useState<Set<string>>(new Set());
  if (!available) return null;

  const visible = trades.filter((trade) => !reported.has(trade.id));
  return (
    <section className="flex flex-col gap-3" aria-label="Shared trades">
      <h2 style={{ font: "var(--font-card-title)" }}>Shared by users</h2>
      {visible.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Nothing shared yet.
        </p>
      ) : (
        visible.map((trade) => (
          <SharedTradeCard
            key={trade.id}
            trade={trade}
            onDelete={onDelete}
            onReport={(id) => {
              setReported((prev) => new Set(prev).add(id));
              void onReport(id);
            }}
          />
        ))
      )}
    </section>
  );
}
