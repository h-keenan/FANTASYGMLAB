"use client";

import { useState } from "react";

import { Sheet } from "@/components/ui/Sheet";
import { BADGES, badgeLegend, badgeTitle, badgesAriaLabel, resolveBadges, type BadgeInput, type BadgeKind, type BadgeTone } from "@/lib/playerBadges";

const TONE_COLOR: Record<BadgeTone, string> = {
  success: "var(--color-success)",
  danger: "var(--color-danger)",
  warning: "var(--color-warning)",
  muted: "var(--color-text-muted)",
  accent: "var(--color-accent)",
  action: "var(--color-action)",
};

/**
 * ONE glyph badge (docs/ui-patterns.md, "PlayerBadge"): a 20px tinted circle (capsule for two characters) carrying a
 * letter or symbol, like Sleeper's purple R. The full word lives in `aria-label` and `title` (a long-press / hover
 * tooltip), never on screen, so a row's tag line stays one short strip. `showDetail` (quick view headers only) adds the
 * detail text beside the glyph ("Out 2 wks"). Same tint recipe as ToneBadge, existing tokens only.
 */
export function PlayerBadge({ kind, detail, showDetail = false, testId }: { kind: BadgeKind; detail?: string | null; showDetail?: boolean; testId?: string }) {
  const spec = BADGES[kind];
  const color = TONE_COLOR[spec.tone];
  const title = badgeTitle({ kind, detail });
  return (
    <span
      role="img"
      aria-label={title}
      title={title}
      data-testid={testId ?? "player-badge"}
      data-badge={kind}
      className="inline-flex shrink-0 items-center justify-center gap-1 text-[0.6875rem] font-extrabold leading-none"
      style={{
        minWidth: 20,
        height: 20,
        padding: showDetail && detail ? "0 8px 0 6px" : "0 5px",
        borderRadius: "var(--radius-pill)",
        background: `color-mix(in srgb, ${color} var(--chip-fill-pct, 15%), transparent)`,
        boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${color} 45%, transparent)`,
        color: `color-mix(in srgb, ${color} 80%, var(--color-text-primary))`,
      }}
    >
      <span aria-hidden="true">{spec.glyph}</span>
      {showDetail && detail ? (
        <span aria-hidden="true" className="font-bold">
          {detail}
        </span>
      ) : null}
    </span>
  );
}

/**
 * A row's badge strip: severity order, context-suppressed kinds hidden, at most `max` glyphs and "+n" for the rest.
 * Not interactive by itself (rows are tappable); pass `onLegend` where the strip is not inside a button (quick view
 * header) to make it a 44px tap target that opens the legend.
 */
export function PlayerBadges({
  badges,
  suppress,
  max,
  showDetail = false,
  onLegend,
  testId = "player-badges",
}: {
  badges: ReadonlyArray<BadgeInput | null | undefined | false>;
  suppress?: ReadonlyArray<BadgeKind>;
  max?: number;
  showDetail?: boolean;
  onLegend?: () => void;
  testId?: string;
}) {
  const r = resolveBadges(badges, { suppress, max });
  if (r.shown.length === 0) return null;
  const strip = (
    <>
      {r.shown.map((b) => (
        <PlayerBadge key={b.kind} kind={b.kind} detail={b.detail} showDetail={showDetail} />
      ))}
      {r.overflow > 0 ? (
        <span className="text-[0.6875rem] font-bold" style={{ color: "var(--color-text-muted)" }} title={r.overflowLabels.join(", ")} aria-hidden="true">
          +{r.overflow}
        </span>
      ) : null}
    </>
  );
  if (onLegend) {
    return (
      <button type="button" onClick={onLegend} aria-label={`${badgesAriaLabel(r)}. What the symbols mean`} data-testid={testId} className="inline-flex items-center gap-1" style={{ minHeight: "var(--touch-target-min)" }}>
        {strip}
      </button>
    );
  }
  return (
    <span className="inline-flex shrink-0 items-center gap-1" data-testid={testId} aria-label={badgesAriaLabel(r)}>
      {strip}
    </span>
  );
}

/** The legend sheet: every symbol (or just `kinds`), its glyph and what it means. */
export function BadgeLegendSheet({ open, onClose, kinds }: { open: boolean; onClose: () => void; kinds?: ReadonlyArray<BadgeKind> }) {
  return (
    <Sheet open={open} onClose={onClose} title="What the symbols mean">
      <ul className="flex flex-col" data-testid="badge-legend">
        {badgeLegend(kinds).map((spec) => (
          <li key={spec.kind} className="flex items-center gap-3 py-2" style={{ borderBottom: "1px solid color-mix(in srgb, var(--color-border) 55%, transparent)" }}>
            <PlayerBadge kind={spec.kind} testId="legend-badge" />
            <span className="flex min-w-0 flex-col leading-tight">
              <span className="text-sm font-bold">{spec.label}</span>
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{spec.legend}</span>
            </span>
          </li>
        ))}
      </ul>
    </Sheet>
  );
}

/** A small "Symbols" key for a list header: opens the legend sheet. */
export function BadgeLegendButton({ kinds }: { kinds?: ReadonlyArray<BadgeKind> }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} aria-label="What the symbols mean" className="inline-flex items-center justify-center gap-1 text-xs font-bold" style={{ color: "var(--color-text-muted)", minHeight: "var(--touch-target-min)", minWidth: "var(--touch-target-min)" }}>
        <span aria-hidden="true">ⓘ</span>
        <span>Key</span>
      </button>
      <BadgeLegendSheet open={open} onClose={() => setOpen(false)} kinds={kinds} />
    </>
  );
}
