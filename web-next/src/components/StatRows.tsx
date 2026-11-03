"use client";

import { useState, type ReactNode } from "react";

import { PercentileExplorerSheet } from "@/components/PercentileExplorerSheet";
import { usePlayerQuickView } from "@/context/PlayerQuickViewContext";
import { ordinal, statPercentileBand } from "@/lib/playerQuickViewPresentation";
import { COLLAPSE_AFTER, type StatRowModel } from "@/lib/statRowsPresentation";

/** One stat as a row: label and value on top, a percentile bar under them, the
 * comparison pool as a caption, an optional trend line. Tapping opens the
 * Percentile Explorer when the row has an explorer key. */
export function StatRow({ row, onExplore }: { row: StatRowModel; onExplore?: (row: StatRowModel) => void }) {
  const band = row.percentile != null ? statPercentileBand(row.percentile) : null;
  const body = (
    <>
      <span className="sr-top">
        <span className="sr-label">{row.label}</span>
        <span className="sr-value">{row.value || "—"}</span>
      </span>
      {row.percentile != null ? (
        <span className="sr-barline">
          <span className="sr-bar" aria-hidden="true">
            <span className={`sr-fill sr-fill--${band}`} style={{ width: `${Math.max(2, Math.min(100, row.percentile))}%` }} />
          </span>
          <span className={`sr-pct sr-pct--${band}`} title={row.caption ? `${ordinal(Math.round(row.percentile))} percentile ${row.caption}` : undefined}>
            {ordinal(Math.round(row.percentile))}
          </span>
        </span>
      ) : null}
      {row.trend ? <span className={`sr-trend sr-trend--${row.trendDirection ?? "unknown"}`}>{row.trend}</span> : null}
    </>
  );
  return row.explorerKey && onExplore ? (
    <button type="button" className="sr sr--tap" aria-label={`${row.label} percentile explorer`} onClick={() => onExplore(row)}>
      {body}
    </button>
  ) : (
    <div className="sr">{body}</div>
  );
}

/** A card of rows with the shared Percentile Explorer behind every tappable
 * row. Long lists show the first few and a "Show all" toggle. */
export function StatRowsCard({
  title,
  caption,
  rows,
  playerId,
  collapseAfter = COLLAPSE_AFTER,
  children,
}: {
  title: string;
  caption?: string | null;
  rows: StatRowModel[];
  playerId?: string;
  collapseAfter?: number;
  /** Extra content above the rows (e.g. the usage flag). */
  children?: ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);
  const [explorer, setExplorer] = useState<{ key: string; label: string } | null>(null);
  const { openPlayer } = usePlayerQuickView();
  if (rows.length === 0 && !children) return null;
  const shown = expanded ? rows : rows.slice(0, collapseAfter);
  return (
    <section className="sr-card" aria-label={title}>
      <header className="sr-head">
        <h3>{title}</h3>
        {caption ? <span className="sr-head-caption">{caption}</span> : null}
      </header>
      {children}
      {shown.length > 0 ? (
        <div className="sr-list">
          {shown.map((row) => (
            <StatRow
              key={row.key}
              row={row}
              onExplore={playerId ? (r) => r.explorerKey && setExplorer({ key: r.explorerKey, label: r.label }) : undefined}
            />
          ))}
        </div>
      ) : null}
      {rows.length > collapseAfter ? (
        <button type="button" className="sr-more" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded}>
          {expanded ? "Show fewer" : `Show all ${rows.length}`}
        </button>
      ) : null}
      {explorer && playerId ? (
        <PercentileExplorerSheet
          playerId={playerId}
          statKey={explorer.key}
          statLabel={explorer.label}
          onClose={() => setExplorer(null)}
          onOpenPlayer={(player) => {
            setExplorer(null);
            openPlayer({ ...player, sourceLabel: "Percentile Explorer" });
          }}
        />
      ) : null}
    </section>
  );
}

/** The few numbers that matter, large, at the top. Same rows, same explorer. */
export function HeadlineTiles({ rows, playerId }: { rows: StatRowModel[]; playerId?: string }) {
  const [explorer, setExplorer] = useState<{ key: string; label: string } | null>(null);
  const { openPlayer } = usePlayerQuickView();
  if (rows.length === 0) return null;
  return (
    <div className="hl-strip" data-testid="headline-tiles">
      {rows.map((row) => {
        const band = row.percentile != null ? statPercentileBand(row.percentile) : null;
        const inner = (
          <>
            <span className="hl-label">{row.label}</span>
            <span className="hl-value">{row.value}</span>
            {row.percentile != null ? (
              <span className={`hl-pct sr-pct--${band}`}>{ordinal(Math.round(row.percentile))} pct</span>
            ) : null}
          </>
        );
        return row.explorerKey && playerId ? (
          <button
            key={row.key}
            type="button"
            className="hl-tile hl-tile--tap"
            aria-label={`${row.label} percentile explorer`}
            onClick={() => setExplorer({ key: row.explorerKey as string, label: row.label })}
          >
            {inner}
          </button>
        ) : (
          <div key={row.key} className="hl-tile">
            {inner}
          </div>
        );
      })}
      {explorer && playerId ? (
        <PercentileExplorerSheet
          playerId={playerId}
          statKey={explorer.key}
          statLabel={explorer.label}
          onClose={() => setExplorer(null)}
          onOpenPlayer={(player) => {
            setExplorer(null);
            openPlayer({ ...player, sourceLabel: "Percentile Explorer" });
          }}
        />
      ) : null}
    </div>
  );
}
