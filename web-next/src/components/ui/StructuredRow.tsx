"use client";

import { useState, type ReactNode } from "react";

import { Sheet } from "@/components/ui/Sheet";
import { seeAllLabel, visibleSignalRows } from "@/lib/draftSignals";

import "./ui.css";

export type StructuredRowPill = { key: string; label: string };

export type StructuredRowProps = {
  /** Crest or avatar. Keep it a fixed 36px box so every row lines up. */
  lead?: ReactNode;
  /** One line, truncated. */
  title: string;
  /** Status chip: label + colour (a CSS colour or var()). */
  chip?: { label: string; color: string } | null;
  /** Two or three metric pills at most. */
  pills?: readonly StructuredRowPill[];
  /** One short line (60 characters at most). The long sentence belongs in `detail`. */
  reason?: string;
  /** Gold outline: the signed-in user's own row. */
  highlight?: boolean;
  /** What a screen reader hears for the row button. */
  spoken?: string;
  /** Sheet heading for the detail. */
  detailTitle?: string;
  /** Sheet body. Without `detail` and `onOpen` the row is not tappable. A tappable row has no chevron (the whole row is the target). */
  detail?: ReactNode;
  /** Custom handler instead of the built-in detail sheet. */
  onOpen?: () => void;
  testId?: string;
};

/**
 * One row of a signal list: crest/avatar + name + status chip + metric pills +
 * one short reason; tapping opens a detail Sheet. It is the
 * replacement for delimiter-joined strings ("Team | Retool | Draft #10 | ...")
 * and generated sentences: every part is its own field, so nothing repeats and
 * nothing is parsed back out of text.
 *
 * Layout is fixed so lists scan: 36px lead, name and pills on the first line,
 * chip and reason on the second, 64px tall at most, 44px minimum tap target.
 */
export function StructuredRow({ lead, title, chip, pills = [], reason, highlight = false, detailTitle, detail, onOpen, testId }: StructuredRowProps) {
  const [open, setOpen] = useState(false);
  const tappable = Boolean(detail || onOpen);
  const body = (
    <>
      {lead ? <span className="ui-srow-lead" aria-hidden="true">{lead}</span> : null}
      <span className="ui-srow-main">
        <span className="ui-srow-line">
          <span className="ui-srow-title">{title}</span>{" "}
          {pills.length ? (
            <span className="ui-srow-pills">
              {pills.map((pill) => (
                <span key={pill.key} className="ui-srow-pill">
                  {pill.label}{" "}
                </span>
              ))}
            </span>
          ) : null}
        </span>
        {chip || reason ? (
          <span className="ui-srow-line">
            {chip ? (
              <span className="ui-srow-chip" style={{ color: chip.color, borderColor: `color-mix(in srgb, ${chip.color} 55%, transparent)` }}>
                {chip.label}
              </span>
            ) : null}
            {chip && reason ? " " : null}
            {reason ? <span className="ui-srow-reason">{reason}</span> : null}
          </span>
        ) : null}
      </span>
    </>
  );
  const className = `ui-srow${highlight ? " ui-srow-me" : ""}${tappable ? " ui-srow-tap" : ""}`;
  return (
    <>
      {tappable ? (
        <button
          type="button"
          className={className}
          aria-haspopup={detail ? "dialog" : undefined}
          data-testid={testId}
          onClick={() => (onOpen ? onOpen() : setOpen(true))}
        >
          {body}
        </button>
      ) : (
        <div className={className} data-testid={testId}>
          {body}
        </div>
      )}
      {detail ? (
        <Sheet open={open} onClose={() => setOpen(false)} title={detailTitle ?? title} size="sm">
          {detail}
        </Sheet>
      ) : null}
    </>
  );
}

/**
 * The first few rows, then "See all (n)" which expands the rest in place
 * (aria-expanded). Nothing is shown for an empty list.
 */
export function StructuredRowList<T>({
  items,
  renderRow,
  top,
  ariaLabel,
}: {
  items: readonly T[];
  renderRow: (item: T, index: number) => ReactNode;
  /** Rows shown before "See all". Default 3. */
  top?: number;
  ariaLabel?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  if (items.length === 0) return null;
  const shown = visibleSignalRows(items, expanded, top);
  const more = seeAllLabel(items.length, top);
  return (
    <div className="ui-srow-list">
      {/* The list holds only list items; the See all button sits beside it (axe aria-required-children). */}
      <div className="ui-srow-list" role="list" aria-label={ariaLabel}>
        {shown.map((item, index) => (
          <div key={index} role="listitem">
            {renderRow(item, index)}
          </div>
        ))}
      </div>
      {more ? (
        <button type="button" className="ui-srow-more" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>
          {expanded ? "Show less" : more}
        </button>
      ) : null}
    </div>
  );
}
