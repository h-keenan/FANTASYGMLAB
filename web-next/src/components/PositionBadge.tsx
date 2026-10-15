import { positionColorVar } from "@/lib/playerPresentation";

/**
 * Colored position pill — ports modules/football_assets.py's
 * position_badge_html. Extracted (Revision 3 CSS-cleanup pass) from three
 * byte-identical inline copies that had drifted into MyTeamContent.tsx's
 * local `PositionBadge`, GamePlanCard.tsx's inline span, and this
 * component's own Trade Hub card use — one definition instead of three
 * copies to keep in sync by hand.
 */
export function PositionBadge({ position }: { position: string | null | undefined }) {
  if (!position) return null;
  const colorVar = positionColorVar(position);
  return (
    <span
      className="px-1.5 py-0.5 text-xs font-bold"
      style={{
        background: colorVar ? `var(${colorVar})` : "var(--color-surface-raised)",
        color: colorVar ? "var(--color-brand-mark-ink)" : "var(--color-text-secondary)",
      }}
    >
      {position}
    </span>
  );
}
