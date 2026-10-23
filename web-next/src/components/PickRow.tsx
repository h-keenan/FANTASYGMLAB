import type { DraftPickAsset } from "@/lib/api";
import { ValueStat } from "@/components/ValueStat";

/**
 * The square draft-pick plate ("R1" over "#3"). Shows the round alone when
 * there is no pick number; nothing is invented.
 */
export function PickPlate({ round, pickNo }: { round?: number | string | null; pickNo?: number | string | null }) {
  const top = round ? `R${round}` : pickNo ? `#${pickNo}` : "PICK";
  const bottom = round && pickNo ? `#${pickNo}` : null;
  return (
    <div
      className="flex flex-col items-center justify-center font-extrabold uppercase leading-none"
      style={{
        width: "2.25rem",
        height: "2.25rem",
        flex: "0 0 2.25rem",
        fontSize: "0.6875rem",
        gap: 2,
        background: "var(--color-surface-muted)",
        border: "var(--border-width-default) solid var(--color-border)",
        color: "var(--color-accent)",
      }}
    >
      <span>{top}</span>
      {bottom ? <span>{bottom}</span> : null}
    </div>
  );
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
