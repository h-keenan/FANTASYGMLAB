import type { DraftPickAsset } from "@/lib/api";
import { PickAvatar } from "@/components/PickAvatar";
import { ValueStat } from "@/components/ValueStat";

/** Draft-pick avatar ("R1" over "#3") in the round player-photo slot. Kept under its old name for existing callers; see PickAvatar. */
export function PickPlate({ round, pickNo, size = 36 }: { round?: number | string | null; pickNo?: number | string | null; size?: number }) {
  return <PickAvatar round={round} pickNo={pickNo} size={size} />;
}

/**
 * The one draft-pick row: PickPlate + label + context line, and an optional
 * value with caption. Used by Draft Center, Players, and trade asset lists.
 * `dense` drops the padding for rows inside another list.
 */
export function PickRow({
  round,
  pickNo,
  label,
  context,
  value,
  caption,
  showDivider = false,
  dense = false,
}: {
  round?: number | string | null;
  pickNo?: number | string | null;
  label?: string | null;
  context?: string | null;
  /** Omit (undefined) to show no value column. */
  value?: number | null;
  caption?: string | null;
  showDivider?: boolean;
  dense?: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-3 ${dense ? "py-1.5" : "px-3 py-2"}`}
      style={showDivider ? { borderBottom: "var(--border-width-default) solid var(--color-border)" } : undefined}
    >
      <PickPlate round={round} pickNo={pickNo} />
      <div className="flex flex-col gap-0.5 min-w-0 mr-auto">
        <span className="text-sm font-bold break-words" style={{ color: "var(--color-text-primary)" }}>
          {label || (round ? `Round ${round}` : "Draft pick")}
        </span>
        {context ? (
          <span className="text-xs break-words" style={{ color: "var(--color-text-muted)" }}>
            {context}
          </span>
        ) : null}
      </div>
      {value !== undefined ? (
        <div className="flex flex-col items-end gap-0.5 shrink-0">
          <ValueStat value={value != null ? Math.round(value) : "—"} />
          {caption ? (
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {caption}
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** Maps a DraftPickAsset (Draft Center / Players) onto PickRow's props. */
export function draftPickRowProps(pick: DraftPickAsset, showOwner: boolean) {
  const confidence =
    typeof pick.projection_confidence === "number" ? Math.round(pick.projection_confidence * 100) : null;
  const context = [pick.pick_tier, pick.projected_pick_range, showOwner ? pick.owner_team_name : null]
    .filter((bit): bit is string => Boolean(bit))
    .join(" · ");
  return {
    round: pick.round,
    label: pick.label,
    context: context || null,
    value: pick.score,
    caption: confidence !== null ? `${confidence}% conf` : null,
  };
}
