"use client";

import { PlayerAvatar } from "@/components/PlayerAvatar";
import { avatarSize, playerHeadshotId, playerInitials, type AvatarTier, type PlayerRef } from "@/lib/playerAnatomy";

/**
 * THE avatar slot of the player anatomy (docs/ui-patterns.md, "Player anatomy"). Every player template renders this
 * itself from a `player`; a module never places an avatar by hand. Size comes from the density tier
 * (`AVATAR_SIZE`), the slot is always first and leading, and a missing or failed photo (generated sim players,
 * rookies) falls back to initials in the tier ring. Mobile twin: components/PlayerAvatarSlot.tsx.
 */
export function PlayerAvatarSlot({ player, tier = "row" }: { player: PlayerRef; tier?: AvatarTier }) {
  const size = avatarSize(tier);
  return (
    <span className="relative flex shrink-0 items-center justify-center" style={{ width: size, height: size }} data-testid="player-avatar-slot" data-avatar-tier={tier}>
      <PlayerAvatar playerId={playerHeadshotId(player)} tier={player.tier ?? undefined} size={size} fallbackLabel={playerInitials(player.name)} />
    </span>
  );
}
