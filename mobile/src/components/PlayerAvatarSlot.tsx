import React from 'react';
import { View } from 'react-native';

import PlayerAvatar from './PlayerAvatar';
import { avatarSize, playerHeadshotId, playerInitials, type AvatarTier, type PlayerRef } from '../lib/playerAnatomy';

/**
 * THE avatar slot of the player anatomy (twin of web-next/src/components/ui/PlayerAvatarSlot.tsx). Every player
 * template renders this itself from a `player`: first, leading, sized by the density tier, initials when there is
 * no photo or it fails to load. A module never places an avatar by hand.
 */
export default function PlayerAvatarSlot({ player, tier = 'row' }: { player: PlayerRef; tier?: AvatarTier }) {
  const size = avatarSize(tier);
  return (
    <View style={{ width: size, height: size }} testID="player-avatar-slot">
      <PlayerAvatar playerId={playerHeadshotId(player)} tier={player.tier ?? undefined} size={size} fallbackLabel={playerInitials(player.name)} />
    </View>
  );
}
