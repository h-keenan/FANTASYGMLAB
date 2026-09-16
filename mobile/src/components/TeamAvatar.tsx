import React, { useState } from 'react';
import { Image, StyleSheet, View, type ImageStyle, type StyleProp, type ViewStyle } from 'react-native';

import { colors } from '../theme';

const SLEEPER_AVATAR_BASE = 'https://sleepercdn.com/avatars/thumbs';

interface TeamAvatarProps {
  avatarId: string | null | undefined;
  size?: number;
  style?: StyleProp<ViewStyle>;
}

/**
 * Sleeper league/team (user) avatars — matches modules/sleeper.py's
 * get_sleeper_avatar_url(thumb=True). A distinct public CDN path from
 * player headshots (avatars/ vs content/nfl/players/).
 */
export default function TeamAvatar({ avatarId, size = 36, style }: TeamAvatarProps) {
  const [failed, setFailed] = useState(false);
  const dimension = { width: size, height: size, borderRadius: size / 2 };

  if (!avatarId || failed) {
    return <View style={[styles.fallback, dimension, style]} />;
  }

  const uri = avatarId.startsWith('http') ? avatarId : `${SLEEPER_AVATAR_BASE}/${avatarId}`;

  return (
    <Image source={{ uri }} style={[dimension, style] as StyleProp<ImageStyle>} onError={() => setFailed(true)} />
  );
}

const styles = StyleSheet.create({
  fallback: {
    backgroundColor: colors.surfaceSolid,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.border,
  },
});
