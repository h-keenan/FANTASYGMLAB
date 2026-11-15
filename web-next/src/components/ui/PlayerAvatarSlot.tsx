"use client";

import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerTap } from "@/components/ui/PlayerOpenContext";
import { PLAYER_TAP_MIN } from "@/lib/playerTap";
import { avatarSize, playerHeadshotId, playerInitials, type AvatarTier, type PlayerRef } from "@/lib/playerAnatomy";

/**
 * THE avatar slot of the player anatomy (docs/ui-patterns.md, "Player anatomy"). Every player template renders this
 * itself from a `player`; a module never places an avatar by hand. Size comes from the density tier
 * (`AVATAR_SIZE`), the slot is always first and leading, and a missing or failed photo (generated sim players,
 * rookies) falls back to initials in the tier ring. Tappable by default (opens the quick view, 44px target): pass
 * `nonInteractive="reason"` only when it sits inside a tap target that already opens the player. Mobile twin:
 * components/PlayerAvatarSlot.tsx.
 */
export function PlayerAvatarSlot({ player, tier = "row", nonInteractive, onOpen, className = "" }: { player: PlayerRef; tier?: AvatarTier; nonInteractive?: string; onOpen?: () => void; className?: string }) {
  const size = avatarSize(tier);
  const slot = (
    <span className="relative flex shrink-0 items-center justify-center" style={{ width: size, height: size }} data-testid="player-avatar-slot" data-avatar-tier={tier}>
      <PlayerAvatar playerId={playerHeadshotId(player)} tier={player.tier ?? undefined} size={size} fallbackLabel={playerInitials(player.name)} />
    </span>
  );
  return (
    <PlayerTap player={player} onOpen={onOpen} nonInteractive={nonInteractive} className={`flex shrink-0 items-center justify-center ${className}`.trim()} style={size < PLAYER_TAP_MIN ? { minWidth: PLAYER_TAP_MIN, marginInline: -(PLAYER_TAP_MIN - size) / 2 } : undefined}>
      {slot}
    </PlayerTap>
  );
}
