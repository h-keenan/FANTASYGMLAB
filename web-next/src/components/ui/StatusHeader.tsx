"use client";

import Link from "next/link";
import { useId, useState, type ReactNode } from "react";

import { AccentCard } from "@/components/AccentCard";
import { ButtonLink, Button } from "@/components/Button";
import { PlayerRow } from "@/components/PlayerRow";
import {
  statusAttentionAria,
  statusHeaderModel,
  type StatusAttentionItem,
  type StatusHeaderModel,
  type StatusMiniStat,
  type StatusRing,
  type StatusTone,
} from "@/lib/statusHeader";

/**
 * THE players-first status header (docs/ui-patterns.md, "StatusHeader"): status ring + three mini stats, then a short
 * "Needs your attention" list of player rows (shared `PlayerRow`, so every row has an avatar), then the one primary
 * action in cyan, then optional CompactModules (`children`). Used on Today, My Team and Fantasy Sim Home; the page
 * hands it a `StatusHeaderModel` built by the pure adapters in lib/statusHeader.ts. Gold is never used here (it is for
 * premium meaning only). Mobile twin: mobile/src/components/StatusHeader.tsx.
 */

const TONE: Record<StatusTone, string> = {
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  accent: "var(--color-accent)",
  muted: "var(--color-text-muted)",
};

export function StatusRingMark({ ring, size = 54 }: { ring: StatusRing; size?: number }) {
  const stroke = 5;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const color = TONE[ring.tone];
  return (
    <span className="relative inline-flex shrink-0 items-center justify-center" style={{ width: size, height: size }} role="img" aria-label={ring.label} data-testid="status-ring" data-pct={ring.pct ?? ""}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-surface-muted)" strokeWidth={stroke} />
        {ring.pct != null ? (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${(c * ring.pct) / 100} ${c}`}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
        ) : null}
      </svg>
      <span className="absolute text-sm font-extrabold tabular-nums" style={{ color: "var(--color-text-primary)" }} aria-hidden="true">
        {ring.center}
      </span>
    </span>
  );
}

function MiniStat({ stat }: { stat: StatusMiniStat }) {
  const body = (
    <>
      <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
        {stat.label}
      </span>
      <span className="truncate text-base font-extrabold tabular-nums" style={{ color: stat.tone ? TONE[stat.tone] : "var(--color-text-primary)" }}>
        {stat.value}
      </span>
    </>
  );
  const className = "glass-surface flex min-w-0 flex-col gap-0.5 px-2.5 py-1.5";
  const style = { minHeight: "var(--touch-target-min)", borderRadius: "var(--radius-card, 12px)", color: "inherit", textDecoration: "none" } as const;
  return stat.href ? (
    <Link href={stat.href} className={className} style={style} aria-label={`${stat.label}: ${stat.value}`} data-testid={`status-stat-${stat.key}`}>
      {body}
    </Link>
  ) : (
    <div className={className} style={style} data-testid={`status-stat-${stat.key}`}>
      {body}
    </div>
  );
}

/** The right edge of an attention row: one figure (or one grade), never a cluster. */
function RowFigure({ item }: { item: StatusAttentionItem }) {
  if (item.grade) {
    return (
      <span className="flex flex-col items-end" data-testid="status-row-grade">
        <span className="text-base font-extrabold" style={{ color: "var(--color-accent)" }}>
          {item.grade}
        </span>
        <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)" }}>
          GRADE
        </span>
      </span>
    );
  }
  if (!item.stat) return null;
  return (
    <span className="flex flex-col items-end">
      <span className="text-base font-extrabold tabular-nums" style={{ color: item.stat.tone ? TONE[item.stat.tone] : "var(--color-text-primary)" }}>
        {item.stat.value}
      </span>
      <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)" }}>
        {item.stat.label}
      </span>
    </span>
  );
}

function AttentionRow({ item, first }: { item: StatusAttentionItem; first: boolean }) {
  const [open, setOpen] = useState(false);
  const panel = useId();
  const row = (
    <PlayerRow
      playerId={item.playerId}
      name={item.name}
      position={item.position}
      tier={item.tier}
      injuryStatus={item.injuryStatus}
      avatarSize={36}
      fallbackLabel={item.name.trim().slice(0, 1)}
      disableQuickView
      className="min-w-0 flex-1"
      trailing={<RowFigure item={item} />}
    >
      {item.meta}
    </PlayerRow>
  );
  const border = first ? undefined : { borderTop: "var(--border-width-default) solid var(--color-border)" };
  if (item.detail) {
    return (
      <li style={border} data-testid="status-attention-row">
        <button
          type="button"
          className="flex w-full items-center gap-1 text-left"
          style={{ minHeight: "var(--touch-target-min)", color: "inherit" }}
          aria-expanded={open}
          aria-controls={panel}
          aria-label={`${statusAttentionAria(item)}. ${open ? "Collapse" : "Expand"}`}
          onClick={() => setOpen(!open)}
        >
          {row}
          <span aria-hidden="true" className="shrink-0 text-xs" style={{ color: "var(--color-text-muted)" }}>
            {open ? "▴" : "▾"}
          </span>
        </button>
        {open ? (
          <div id={panel} className="flex flex-col gap-1 pb-2 pl-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
            <p className="m-0">{item.detail}</p>
            {item.href ? (
              <Link href={item.href} className="tap-link text-xs font-bold" style={{ color: "var(--color-accent)", textDecoration: "none" }}>
                Open →
              </Link>
            ) : null}
          </div>
        ) : null}
      </li>
    );
  }
  return (
    <li style={border} data-testid="status-attention-row">
      {item.href ? (
        <Link href={item.href} className="flex w-full items-center gap-1" style={{ minHeight: "var(--touch-target-min)", color: "inherit", textDecoration: "none" }} aria-label={statusAttentionAria(item)}>
          {row}
          <span aria-hidden="true" data-row-arrow style={{ color: "var(--color-accent)" }}>
            →
          </span>
        </Link>
      ) : (
        <div className="flex w-full items-center" style={{ minHeight: "var(--touch-target-min)" }} aria-label={statusAttentionAria(item)}>
          {row}
        </div>
      )}
    </li>
  );
}

export function StatusHeader({
  model: raw,
  attentionTitle = "Needs your attention",
  badge,
  headerHref,
  onAction,
  actionLoading = false,
  testId = "status-header",
  children,
}: {
  model: StatusHeaderModel;
  attentionTitle?: string;
  /** A small pill beside the kicker (archetype, status). */
  badge?: ReactNode;
  /** Makes the ring + headline block a link (Today: the matchup page). */
  headerHref?: string;
  /** Handles a primary action that has an `actionKey` instead of an href (the sim switches tabs). */
  onAction?: (actionKey: string) => void;
  actionLoading?: boolean;
  testId?: string;
  /** CompactModules that follow the header (the "optional CompactModules" of the stack). */
  children?: ReactNode;
}) {
  const model = statusHeaderModel(raw);
  const top = (
    <>
      {model.ring ? <StatusRingMark ring={model.ring} /> : null}
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="flex items-center gap-2">
          <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-accent)", letterSpacing: "var(--letter-spacing-badge)" }}>
            {model.kicker}
          </span>
          {badge}
        </span>
        <span className="text-base font-extrabold leading-snug" data-testid="status-headline">
          {model.headline}
        </span>
        {model.context ? (
          <span className="text-sm leading-snug" style={{ color: "var(--color-text-secondary)" }} data-testid="status-context">
            {model.context}
          </span>
        ) : null}
      </span>
    </>
  );
  const primary = model.primary;
  return (
    <section className="flex flex-col gap-2" data-testid={testId} aria-label={model.kicker}>
      <AccentCard accent="var(--color-accent-strong)" as="div">
        {headerHref ? (
          <Link href={headerHref} className="flex items-center gap-3" style={{ minHeight: "var(--touch-target-min)", color: "inherit", textDecoration: "none" }} aria-label={[model.kicker, model.headline, model.context].filter(Boolean).join(". ")}>
            {top}
          </Link>
        ) : (
          <div className="flex items-center gap-3">{top}</div>
        )}
        {model.stats.length > 0 ? (
          <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${model.stats.length}, minmax(0, 1fr))` }} data-testid="status-stats">
            {model.stats.map((stat) => (
              <MiniStat key={stat.key} stat={stat} />
            ))}
          </div>
        ) : null}
        {model.attention.length > 0 ? (
          <div className="flex flex-col" data-testid="status-attention">
            <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
              {attentionTitle}
            </span>
            <ul className="m-0 flex list-none flex-col p-0">
              {model.attention.map((item, index) => (
                <AttentionRow key={item.key} item={item} first={index === 0} />
              ))}
            </ul>
          </div>
        ) : null}
        {primary ? (
          primary.href ? (
            <ButtonLink href={primary.href} variant="primary" fullWidth data-testid="status-primary">
              {primary.label}
            </ButtonLink>
          ) : (
            <Button variant="primary" fullWidth loading={actionLoading} onClick={() => primary.actionKey && onAction?.(primary.actionKey)} data-testid="status-primary">
              {primary.label}
            </Button>
          )
        ) : null}
      </AccentCard>
      {children}
    </section>
  );
}
