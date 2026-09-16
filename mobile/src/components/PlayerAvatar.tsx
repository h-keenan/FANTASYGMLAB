import React, { useState } from 'react';
import { Image, StyleSheet, View, type ImageStyle, type StyleProp, type ViewStyle } from 'react-native';

import { colors } from '../theme';

const SLEEPER_HEADSHOT_BASE = 'https://sleepercdn.com/content/nfl/players';

interface PlayerAvatarProps {
  playerId: string | null | undefined;
  size?: number;
  style?: StyleProp<ViewStyle>;
}

/**
 * Sleeper's headshot CDN is public and keyed by player_id — no backend proxy
 * needed (matches modules/player_images.py's get_player_headshot_url on the
 * web app). Many players (rookies, IDP, deep bench) have no photo on file,
 * so a load failure quietly falls back to a blank avatar circle rather than
 * a broken-image icon.
 */
export default function PlayerAvatar({ playerId, size = 40, style }: PlayerAvatarProps) {
  const [failed, setFailed] = useState(false);
  const dimension = { width: size, height: size, borderRadius: size / 2 };

  if (!playerId || failed) {
    return <View style={[styles.fallback, dimension, style]} />;
  }

  return (
    <Image
      source={{ uri: `${SLEEPER_HEADSHOT_BASE}/${playerId}.jpg` }}
      style={[dimension, style] as StyleProp<ImageStyle>}
      onError={() => setFailed(true)}
    />
  );
}

const styles = StyleSheet.create({
  fallback: {
    backgroundColor: colors.surfaceSolid,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
});
