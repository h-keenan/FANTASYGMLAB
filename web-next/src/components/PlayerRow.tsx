import type { ReactNode } from "react";

import type { PlayerQuickViewIdentity } from "@/context/PlayerQuickViewContext";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PlayerMetaLine } from "@/components/PlayerInjuryBadge";
import { PositionBadge } from "@/components/PositionBadge";
import { PlayerName } from "@/components/PlayerName";
import { rowAffordance } from "@/lib/rowAffordance";

/**
 * The standard left half of every player row: position badge, 40px avatar,
 * bold name, then a muted subline with the injury pill beside it. Replaces
 * the ten local copies that each restated this markup with slightly
 * different gaps. Wraps itself in `PlayerIdentityTrigger` (opens Player
 * Quick View) when `identity` is given; pass `disableQuickView` when the
 * row already sits inside its own button.
 */
export function PlayerIdentity({
  identity,
  playerId,
  name,
  position,
  tier,
  injuryStatus,
  muted = false,
  disableQuickView = false,
  avatarSize = 40,
  fallbackLabel,
  leading,
  after,
  className = "min-w-0",
  rowHit = false,
  children,
}: {
  /** Quick View payload. Omit for a non-interactive identity. */
  identity?: PlayerQuickViewIdentity | null;
  playerId?: string | null;
  name: string;
  position?: string | null;
  tier?: string | null;
  injuryStatus?: string | null;
  /** Bench / secondary rows render the name in the secondary color. */
  muted?: boolean;
  disableQuickView?: boolean;
  avatarSize?: number;
  /** Initials shown in the avatar ring when the player has no photo. */
  fallbackLabel?: string | null;
  /** Node before the badge (e.g. an overall-rank number). */
  leading?: ReactNode;
  /** Extra line under the subline (e.g. a trending tag). */
  after?: ReactNode;
  /** Wrapper classes; pass "flex-1 min-w-0" to make the identity fill the row. */
  className?: string;
  /** Stretch the Quick View trigger over the whole row (PlayerRow sets this): no chevron needed, see lib/rowAffordance.ts. */
  rowHit?: boolean;
  /** Subline content ("MIA · Age 23"). */
  children?: ReactNode;
}) {
  const body = (
    <>
      {leading}
      <PositionBadge position={position} />
      <PlayerAvatar playerId={playerId ?? undefined} tier={tier ?? undefined} size={avatarSize} fallbackLabel={fallbackLabel} />
      <div className="flex flex-col gap-0.5 min-w-0">
        <PlayerName
          name={name}

          className="text-sm font-bold"
          style={{ color: muted ? "var(--color-text-secondary)" : "var(--color-text-primary)" }}
        />
        <PlayerMetaLine injuryStatus={injuryStatus}>{children}</PlayerMetaLine>
        {after}
      </div>
    </>
  );
  if (identity && !disableQuickView) {
    return (
      <PlayerIdentityTrigger identity={identity} className={`flex items-center gap-3 ${rowHit ? "row-hit " : ""}${className}`.trim()} noPress={rowHit}>
        {body}
      </PlayerIdentityTrigger>
    );
  }
  return <div className={`flex items-center gap-3 ${className}`}>{body}</div>;
}

/**
 * A full player row: `PlayerIdentity` on the left, a trailing slot on the
 * right (gauges, `ValueStat`, actions). `bordered` adds the hairline divider
 * list rows use.
 */
export function PlayerRow({
  trailing,
  bordered = false,
  className = "",
  ...identityProps
}: Parameters<typeof PlayerIdentity>[0] & {
  trailing?: ReactNode;
  bordered?: boolean;
  className?: string;
}) {
  // With a Quick View identity the whole row is the target (rule: lib/rowAffordance.ts). No chevron.
  const whole = rowAffordance({ rowAction: identityProps.identity && !identityProps.disableQuickView ? "player" : null }).wholeRow;
  return (
    <div
      className={`flex items-center justify-between gap-3 py-2 ${whole ? "row-hit-scope " : ""}${className}`.trim()}
      style={bordered ? { borderBottom: "var(--border-width-default) solid var(--color-border)" } : undefined}
    >
      <PlayerIdentity {...identityProps} rowHit={whole} />
      {trailing ? <div className="flex items-center gap-2 shrink-0">{trailing}</div> : null}
    </div>
  );
}
