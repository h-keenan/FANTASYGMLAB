"use client";

import { useEffect, useState } from "react";

import { EmptyState } from "@/components/EmptyState";
import { PillRow } from "@/components/PillRow";
import { PlayerIdentity } from "@/components/PlayerRow";
import { CompactModule } from "@/components/ui/CompactModule";
import { listSummaryParts } from "@/lib/moduleTemplates";
import { SkeletonBlock } from "@/components/Skeleton";
import { api, type ValueSignalItem, type ValueSignalsResponse } from "@/lib/api";
import { formatRatingDelta, signalReason, signalsStatusMessage } from "@/lib/valueHistoryPresentation";

type Tab = "buy_low" | "sell_high";

/**
 * Buy low / Sell high on the Trade Hub: players whose value rating moved
 * against how they are actually producing (GET /v1/players/value-signals,
 * from the real daily rating snapshots). Hidden when the value history is
 * unreadable; says how many days of history exist while it is still building.
 * Mirrors mobile's ValueSignalsCard.
 */
export function ValueSignalsCard({ leagueId }: { leagueId: string }) {
  const [data, setData] = useState<ValueSignalsResponse | null>(null);
  const [tab, setTab] = useState<Tab>("buy_low");

  useEffect(() => {
    let cancelled = false;
    api
      .getPlayerValueSignals()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!data) return <SkeletonBlock height={96} />;
  if (data.status === "unavailable") return null;
  const status = signalsStatusMessage(data);
  const items = tab === "buy_low" ? data.buy_low : data.sell_high;
  const parts = status
    ? [{ key: "s", text: status }]
    : listSummaryParts({
        count: data.buy_low.length + data.sell_high.length,
        noun: "signal",
        none: "No buy-low or sell-high candidates",
        highlights: [`${data.buy_low.length} buy low`, `${data.sell_high.length} sell high`, data.buy_low[0]?.name ?? data.sell_high[0]?.name],
        maxHighlights: 3,
      });
  return (
    <CompactModule id="trades.signals" title="Buy low / Sell high" testId="value-signals" tone="accent" parts={parts}>
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Value rating trend against this season&apos;s production.</p>
      {!status && data.buy_low.length === 0 && data.sell_high.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }} data-testid="value-signals-none">
          No buy-low or sell-high candidates right now. Nobody clears both the value-trend and production bars.
        </p>
      ) : status ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          {status}
        </p>
      ) : (
        <>
          <PillRow
            options={[
              { value: "buy_low", label: `Buy low (${data.buy_low.length})` },
              { value: "sell_high", label: `Sell high (${data.sell_high.length})` },
            ]}
            active={tab}
            onSelect={(value) => setTab(value as Tab)}
            fullWidth
            ariaLabel="Buy low or sell high"
          />
          {items.length === 0 ? (
            <EmptyState
              title={tab === "buy_low" ? "No buy-low candidates" : "No sell-high candidates"}
              subtitle="Nobody currently clears both the value-trend and production bars."
            />
          ) : (
            <div className="flex flex-col gap-2">
              {items.map((item) => (
                <SignalRow key={item.player_id} item={item} leagueId={leagueId} />
              ))}
            </div>
          )}
          {data.method ? (
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {data.method} Based on {data.span_days} days of stored value history.
            </p>
          ) : null}
        </>
      )}
    </CompactModule>
  );
}

function SignalRow({ item, leagueId }: { item: ValueSignalItem; leagueId: string }) {
  const good = item.signal === "buy_low";
  return (
    <div className="glass-surface flex items-center justify-between gap-3 p-3">
      <PlayerIdentity
        identity={{
          player_id: item.player_id,
          name: item.name,
          position: item.position,
          team: item.team,
          age: item.age,
          injury_status: item.injury_status,
          leagueId,
        }}
        playerId={item.player_id}
        name={item.name}
        position={item.position}
        injuryStatus={item.injury_status}
        className="min-w-0 flex-1"
      >
        {item.team} · {signalReason(item)}
      </PlayerIdentity>
      <span
        className="text-sm font-extrabold shrink-0"
        style={{ color: good ? "var(--color-success)" : "var(--color-danger)", fontVariantNumeric: "tabular-nums" }}
      >
        {formatRatingDelta(item.rating_change)}
      </span>
    </div>
  );
}
