import React from 'react';
import { View } from 'react-native';

import PlayerAvatar from './PlayerAvatar';
import { PlayerTap } from './PlayerOpenContext';
import { avatarSize, playerHeadshotId, playerInitials, type AvatarTier, type PlayerRef } from '../lib/playerAnatomy';

/**
 * THE avatar slot of the player anatomy (twin of web-next/src/components/ui/PlayerAvatarSlot.tsx). Every player
 * template renders this itself from a `player`: first, leading, sized by the density tier, initials when there is
 * no photo or it fails to load. A module never places an avatar by hand. Tappable by default (opens the quick view); pass
 * `nonInteractive="reason"` only inside a tap target that already opens the player.
 */
export default function PlayerAvatarSlot({ player, tier = 'row', nonInteractive, onOpen }: { player: PlayerRef; tier?: AvatarTier; nonInteractive?: string; onOpen?: () => void }) {
  const size = avatarSize(tier);
  const slot = (
    <View style={{ width: size, height: size }} testID="player-avatar-slot">
      <PlayerAvatar playerId={playerHeadshotId(player)} tier={player.tier ?? undefined} size={size} fallbackLabel={playerInitials(player.name)} name={player.name} position={player.position} team={player.team} />
    </View>
  );
  return (
    <PlayerTap player={player} onOpen={onOpen} nonInteractive={nonInteractive} minHeight={size}>
      {slot}
    </PlayerTap>
  );
}
