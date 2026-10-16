import type { DraftPickAsset } from "@/lib/api";

/**
 * Single draft-pick row (label, tier/range/owner context, score, projection
 * confidence) — extracted from DraftCenterContent.tsx's local `PickRow`
 * (Revision 14) so the Players/Picks toggle (Revision 17) reads the same
 * row convention instead of inventing a second one. Visual output is
 * unchanged from the original.
 */
export function PickRow({
  pick,
  showOwner,
  showDivider,
}: {
  pick: DraftPickAsset;
  showOwner: boolean;
  showDivider: boolean;
}) {
  const confidence =
    typeof pick.projection_confidence === "number" ? Math.round(pick.projection_confidence * 100) : null;
  const contextBits = [pick.pick_tier, pick.projected_pick_range, showOwner ? pick.owner_team_name : null].filter(
    (bit): bit is string => Boolean(bit),
  );

  return (
    <div
      className="flex items-center justify-between gap-3 px-3 py-2"
      style={showDivider ? { borderBottom: "var(--border-width-default) solid var(--color-border)" } : undefined}
    >
      <div className="flex flex-col gap-0.5 min-w-0">
        <span className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
          {pick.label || `Round ${pick.round ?? "?"}`}
        </span>
        {contextBits.length > 0 ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {contextBits.join(" · ")}
          </span>
        ) : null}
      </div>
      <div className="flex flex-col items-end gap-0.5 shrink-0">
        <span className="text-sm font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {pick.score != null ? Math.round(pick.score) : "—"}
        </span>
        {confidence !== null ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {confidence}% conf
          </span>
        ) : null}
      </div>
    </div>
  );
}
