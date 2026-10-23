"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, type ManagerRecentTradeAsset, type ManagerTendenciesDetailResponse } from "@/lib/api";
import { AccentCard } from "@/components/AccentCard";
import { TeamAvatar } from "@/components/TeamAvatar";
import { SectionHeading } from "@/components/SectionHeading";
import { StatStrip } from "@/components/StatStrip";
import { ToneBadge } from "@/components/ToneBadge";
import { gradeToneColor, sampleFill, TENDENCY_SIGNALS, tendencyBadgeText, tendencyTone, tradeDateLabel } from "@/lib/managerTendencies";
import { SheetHandle } from "@/components/SheetHandle";
import { PositionBadge } from "@/components/PositionBadge";
import { PickPlate } from "@/components/PickRow";

function TradeAssetLine({ asset }: { asset: ManagerRecentTradeAsset }) {
  if (asset.kind === "pick") {
    return (
      <div className="flex items-center gap-2 min-w-0">
        <PickPlate round={asset.round} />
        <span className="text-sm font-bold break-words">{asset.label || "Draft pick"}</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2 min-w-0">
      <PositionBadge position={asset.position} />
      <span className="text-sm font-bold break-words">{asset.name}</span>
      {asset.team ? (
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {asset.team}
        </span>
      ) : null}
    </div>
  );
}

function RecentTrades({ trades }: { trades: NonNullable<ManagerTendenciesDetailResponse["recent_trades"]> }) {
  return (
    <>
      <SectionHeading>Recent trades</SectionHeading>
      <ul className="flex flex-col gap-2">
        {trades.map((trade) => (
          <li key={trade.transaction_id}>
            <AccentCard accent="var(--color-border)" compact as="div">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {tradeDateLabel(trade.date, trade.week)}
                  {trade.partners.length ? ` · with ${trade.partners.join(", ")}` : ""}
                </span>
                {trade.grade ? (
                  <ToneBadge label={trade.grade.letter} color={gradeToneColor(trade.grade.tone)} />
                ) : null}
              </div>
              {(
                [
                  ["Got", trade.received],
                  ["Sent", trade.sent],
                ] as Array<[string, ManagerRecentTradeAsset[]]>
              ).map(([label, assets]) =>
                assets.length ? (
                  <div key={label} className="flex flex-col gap-1">
                    <span
                      className="text-xs uppercase font-extrabold"
                      style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
                    >
                      {label}
                    </span>
                    {assets.map((asset, i) => (
                      <TradeAssetLine key={`${asset.player_id ?? asset.label}-${i}`} asset={asset} />
                    ))}
                  </div>
                ) : null,
              )}
            </AccentCard>
          </li>
        ))}
      </ul>
    </>
  );
}

/** Manager profile sheet (League Rankings): every readable signal with its
 * evidence line. Loaded only when opened. Reuses the quick-view sheet shell. */
export function ManagerProfileSheet({
  leagueId,
  rosterId,
  teamName,
  ownerName,
  avatarUrl,
  onClose,
}: {
  leagueId: string;
  rosterId: string | number;
  teamName: string;
  ownerName?: string | null;
  avatarUrl?: string | null;
  onClose: () => void;
}) {
  const [data, setData] = useState<ManagerTendenciesDetailResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getManagerTendencyDetail(leagueId, rosterId)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, rosterId]);

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  const signals = data?.manager?.signals ?? {};
  const sample = data?.manager?.sample ?? null;
  const rows = TENDENCY_SIGNALS.filter(([key]) => signals[key]?.status === "ok");

  return (
    <div
      className="pqv-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="pqv-modal" role="dialog" aria-modal="true" aria-labelledby="mgr-profile-name">
        <SheetHandle />
        <button type="button" className="pqv-close" aria-label="Close manager profile" onClick={onClose}>
          ×
        </button>
        <div className="pqv-scroll">
          <div className="flex items-center gap-3 pr-10">
            <TeamAvatar avatarUrl={avatarUrl} name={ownerName || teamName} size={48} />
            <div className="flex min-w-0 flex-col gap-0.5">
              <h2 id="mgr-profile-name" className="text-lg font-extrabold break-words">
                {teamName}
              </h2>
              {ownerName ? (
                <span className="text-xs break-words" style={{ color: "var(--color-text-muted)" }}>
                  {ownerName}
                </span>
              ) : null}
            </div>
          </div>
          {failed ? (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              Couldn&apos;t load this profile.
            </p>
          ) : !data ? (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              Loading…
            </p>
          ) : !data.is_premium ? (
            <div className="flex flex-col gap-2">
              <p className="text-sm font-bold">{data.upsell?.title ?? "Manager Tendencies"}</p>
              <Link href="/premium" className="text-sm font-bold self-start" style={{ color: "var(--color-premium)" }}>
                Upgrade →
              </Link>
            </div>
          ) : rows.length === 0 ? (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              Not enough trade history yet.
            </p>
          ) : (
            <div className="flex flex-col gap-3">
              {sample ? (
                <StatStrip
                  columns={3}
                  items={[
                    { glyph: "record", label: "Trades", value: String(sample.trades), tone: "positive" },
                    { glyph: "power", label: "Wire moves", value: String(sample.wire_moves) },
                    { glyph: "age", label: "Seasons", value: String(sample.seasons) },
                  ]}
                />
              ) : null}
              <SectionHeading>Tendencies</SectionHeading>
              <ul className="flex flex-col gap-2">
                {rows.map(([key, title]) => {
                  const signal = signals[key];
                  const tone = `var(--color-${tendencyTone(signal.label)})`;
                  const badge = tendencyBadgeText(signal.label);
                  return (
                    <li key={key}>
                      <AccentCard accent={tone} compact as="div">
                        <div className="flex items-center justify-between gap-2">
                          <span
                            className="text-xs uppercase font-extrabold"
                            style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
                          >
                            {title}
                          </span>
                          {badge ? <ToneBadge label={badge} color={tone} /> : null}
                        </div>
                        <span className="text-sm font-semibold">{signal.summary}</span>
                        <div className="flex items-center gap-2">
                          <div
                            className="flex-1 h-1 overflow-hidden"
                            style={{ background: "var(--color-surface-muted)", borderRadius: "var(--radius-pill)" }}
                            role="presentation"
                          >
                            <div
                              className="h-full"
                              style={{
                                width: `${Math.round(sampleFill(signal.sample_size, signal.min_sample) * 100)}%`,
                                background: tone,
                                borderRadius: "var(--radius-pill)",
                              }}
                            />
                          </div>
                          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                            {signal.sample_size} trade{signal.sample_size === 1 ? "" : "s"}
                          </span>
                        </div>
                      </AccentCard>
                    </li>
                  );
                })}
              </ul>
              {data.recent_trades && data.recent_trades.length > 0 ? (
                <RecentTrades trades={data.recent_trades} />
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
