import React, { useState } from 'react';
import { StyleSheet, View, type ImageStyle, type StyleProp, type ViewStyle } from 'react-native';
import { Image } from 'expo-image';

import { colors } from '../theme';
import { resolvePlayerTier } from '../lib/playerTier';

const SLEEPER_HEADSHOT_BASE = 'https://sleepercdn.com/content/nfl/players';

interface PlayerAvatarProps {
  playerId: string | null | undefined;
  size?: number;
  tier?: string | null;
  style?: StyleProp<ViewStyle>;
}

/**
 * Sleeper's headshot CDN is public and keyed by player_id — no backend proxy
 * needed (matches modules/player_images.py's get_player_headshot_url on the
 * web app). Many players (rookies, IDP, deep bench) have no photo on file,
 * so a load failure quietly falls back to a blank avatar circle rather than
 * a broken-image icon.
 *
 * When `tier` is passed, the avatar gets a colored ring matching the same
 * prestige-tier ladder the web app's portrait frames use (see
 * modules/player_tier_identity.py's portrait_frame_classes).
 *
 * Headshots rarely change and this component re-renders across nearly every
 * list screen, so `expo-image`'s disk cache (persists across app restarts,
 * unlike RN's own `Image`) avoids re-fetching the same photo every time.
 */
export default function PlayerAvatar({ playerId, size = 40, tier, style }: PlayerAvatarProps) {
  const [failed, setFailed] = useState(false);
  const dimension = { width: size, height: size, borderRadius: size / 2 };
  const ringColor = tier ? resolvePlayerTier(tier).color : colors.border;
  const ring = { borderWidth: tier ? 2 : StyleSheet.hairlineWidth, borderColor: ringColor };

  if (!playerId || failed) {
    return <View style={[styles.fallback, dimension, ring, style]} />;
  }

  return (
    <Image
      source={{ uri: `${SLEEPER_HEADSHOT_BASE}/${playerId}.jpg` }}
      style={[dimension, ring, style] as StyleProp<ImageStyle>}
      cachePolicy="disk"
      onError={() => setFailed(true)}
    />
  );
}

const styles = StyleSheet.create({
  fallback: {
    backgroundColor: colors.surfaceSolid,
  },
});
