import { positionBadgeLabel, positionColorVar } from "@/lib/playerPresentation";

/**
 * The single shared position pill (owner decision, 2026-10-22, option A):
 * fully rounded (--radius-pill), tinted by a fixed semantic color per
 * position (QB/RB/WR/TE/K/DEF + IDP DL/LB/DB + a neutral lane for FLEX /
 * SUPERFLEX / IDP_FLEX / BN / IR), tight uppercase tracking, and a min-width
 * so 1-, 2- and 3-letter positions have the same width feel. Styles live in
 * globals.css (`.position-badge*`); mobile/src/components/PositionBadge.tsx
 * and lib/shareCard/frame.tsx's SharePositionBadge mirror this look.
 *
 * `rank` appends a position rank ("RB12") inside the same pill.
 */
export function PositionBadge({
  position,
  size = "sm",
  rank,
  title,
  label,
}: {
  position: string | null | undefined;
  size?: "sm" | "md";
  rank?: number | string | null;
  title?: string;
  /** Override the pill text (e.g. a numbered slot like "RB2"). */
  label?: string;
}) {
  if (!position) return null;
  const colorVar = positionColorVar(position);
  return (
    <span
      className={`position-badge position-badge-${size}`}
      style={colorVar ? ({ "--pb": `var(${colorVar})` } as React.CSSProperties) : undefined}
      title={title}
    >
      {label ?? positionBadgeLabel(position)}
      {rank != null && rank !== "" ? rank : null}
    </span>
  );
}
