"use client";

import { useId, useState, type ReactNode } from "react";

import { OvrGauge } from "@/components/OvrGauge";
import { CompactPlayerCard } from "@/components/ui/CompactPlayerCard";
import { PickTap } from "@/components/ui/PickTap";
import { PickAvatar } from "@/components/PickAvatar";
import { FairnessMeterRow } from "@/components/ui/FairnessMeterRow";
import { SkeletonTradeCard } from "@/components/Skeleton";
import { avatarSize, fairnessMeter, type FairnessMeter, type PlayerMode, type PlayerRef } from "@/lib/playerAnatomy";
import { Collapse, PresenceSwap } from "@/components/ui/Presence";
import { TradeResolvedRow } from "@/components/ui/TradeResolvedRow";

export interface TradeCardAsset {
  key: string;
  /** A player renders as a compact player card (avatar included); a pick passes `pickLabel`. */
  player?: PlayerRef;
  pickLabel?: string;
  detail?: string | null;
  /** Desk only: the asset's value, shown as the card's trailing number. */
  value?: number | null;
  /** Desk only: overall rating gauge beside the value. */
  ovr?: number | null;
  /** Overrides the default tap (the shared opener: Desk PQV, or the sim's PQV inside Fantasy Sim). */
  onOpen?: () => void;
  /** A pick: its id (the sim pick sheet) and an override opener. */
  pickId?: string;
  pickDetail?: string | null;
  onOpenPick?: () => void;
  /** Opt out of the tap, with the reason (a picker row that selects). */
  nonInteractive?: string;
}

/** One asset as a compact player card (avatar included, tap opens the sheet) or a pick row with the round pick avatar. Shared by the trade card and the builder. */
export function TradeAssetCard({ asset: a, mode }: { asset: TradeCardAsset; mode: PlayerMode }) {
  if (a.player) {
    return (
      <CompactPlayerCard
        player={a.player}
        onOpen={a.onOpen}
        nonInteractive={a.nonInteractive}
        detail={a.detail}
        trailing={
          mode === "desk" && (a.value != null || a.ovr != null) ? (
            <span className="inline-flex items-center gap-1.5">
              {a.ovr != null ? <OvrGauge rating={a.ovr} size="sm" /> : null}
              {a.value != null ? Math.round(a.value).toLocaleString() : null}
            </span>
          ) : undefined
        }
      />
    );
  }
  return (
    <PickTap label={a.pickLabel ?? ""} id={a.pickId} detail={a.pickDetail} onOpen={a.onOpenPick} nonInteractive={a.nonInteractive}>
      <div className="flex items-center gap-2 text-sm font-bold" style={{ minHeight: 44 }} data-testid="trade-pick-row">
        <span className="shrink-0"><PickAvatar label={a.pickLabel} size={avatarSize("row")} /></span>
        <span className="min-w-0 flex-1 [overflow-wrap:normal]">{a.pickLabel}</span>
      </div>
    </PickTap>
  );
}

function Side({ label, assets, mode }: { label: string; assets: TradeCardAsset[]; mode: PlayerMode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1" data-testid={`trade-side-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>{label}</span>
      {assets.map((a) => (
        <TradeAssetCard key={a.key} asset={a} mode={mode} />
      ))}
    </div>
  );
}

/**
 * Trade card (idea / offer / inbox): the involved players as compact player cards on a give and a get side, a
 * fairness meter row (recommended V3), and details that expand in place. `mode="sim"` shows plain words and grades,
 * never the hidden value. Shared by Trade Hub, Trade Finder, GM Plan and the Sim trade inbox. Mobile twin:
 * components/TradeCompactCard.tsx.
 */
export function TradeCompactCard({
  title,
  give,
  get,
  mode = "desk",
  verdictLabel,
  netValue,
  children,
  defaultOpen = false,
  testId = "trade-compact-card",
  giveLabel = "You send",
  getLabel = "You get",
  meta = [],
  meter: meterOverride,
  resolved,
}: {
  title: ReactNode;
  give: TradeCardAsset[];
  get: TradeCardAsset[];
  mode?: PlayerMode;
  /** Overrides the meter's computed label (e.g. the server's value-edge band). */
  verdictLabel?: string | null;
  /** The server's net value for the trade (positive = you win); wins over the asset sums, which can miss pick values. */
  netValue?: number | null;
  /** Details shown when expanded (reasoning, odds, share). */
  children?: ReactNode;
  defaultOpen?: boolean;
  testId?: string;
  giveLabel?: string;
  getLabel?: string;
  /** Short facts under the title (e.g. "High confidence"). */
  meta?: string[];
  /** Replaces the computed fairness meter; null hides it (a card whose verdict is stated elsewhere, e.g. their counter). */
  meter?: FairnessMeter | null;
  /** The card was answered (accepted / declined): it collapses into one `TradeResolvedRow` instead of vanishing. */
  resolved?: { kind: "accepted" | "declined"; label: string } | null;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const bodyId = useId();
  const sum = (xs: TradeCardAsset[]) => xs.reduce((n, a) => n + (a.value ?? 0), 0);
  const meter = meterOverride === undefined ? fairnessMeter(sum(give), sum(get), mode, netValue) : meterOverride;
  const hasBody = children != null && children !== false;
  return (
    <section className="glass-surface flex min-w-0 flex-col gap-2 p-3" data-testid={testId} style={{ borderRadius: "var(--radius-panel)" }}>
      <PresenceSwap swapKey={resolved ? "resolved" : "open"} className="flex min-w-0 flex-col gap-2">
      {resolved ? <TradeResolvedRow kind={resolved.kind} label={resolved.label} /> : <>
      <div className="min-w-0 text-sm font-extrabold">{title}</div>
      {meta.length > 0 ? <div className="text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="trade-card-meta">{meta.join(" · ")}</div> : null}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <Side label={giveLabel} assets={give} mode={mode} />
        <Side label={getLabel} assets={get} mode={mode} />
      </div>
      {meter ? <FairnessMeterRow meter={meter} ariaLabel={verdictLabel && mode === "desk" ? `${meter.description}. Market read: ${verdictLabel}` : undefined} /> : null}
      {hasBody ? (
        <>
          <button
            type="button"
            aria-expanded={open}
            aria-controls={bodyId}
            onClick={() => setOpen((v) => !v)}
            className="self-start text-xs font-bold"
            style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)" }}
          >
            {open ? "Hide details" : "Show details"}
          </button>
          <Collapse open={open} id={bodyId}>
            <div className="flex flex-col gap-3">{children}</div>
          </Collapse>
        </>
      ) : null}
      </>}
      </PresenceSwap>
    </section>
  );
}

/** The loading silhouette of a `TradeCompactCard` (title, give and get avatar rows, meter). */
export function TradeCompactCardSkeleton({ assets = 2 }: { assets?: number }) {
  return <SkeletonTradeCard assets={assets} />;
}
