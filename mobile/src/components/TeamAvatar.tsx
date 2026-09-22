import React, { useMemo, useState } from 'react';
import { StyleSheet, View, type ImageStyle, type StyleProp, type ViewStyle } from 'react-native';
import { Image } from 'expo-image';

import { useThemeMode } from '../context/ThemeModeContext';
import type { ThemeColors } from '../theme';

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
 *
 * Team avatars almost never change mid-season and render on every roster
 * row, so `expo-image`'s disk cache (persists across app restarts, unlike
 * RN's own `Image`) avoids re-fetching the same avatar every time.
 */
export default function TeamAvatar({ avatarId, size = 36, style }: TeamAvatarProps) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [failed, setFailed] = useState(false);
  const dimension = { width: size, height: size, borderRadius: size / 2 };

  if (!avatarId || failed) {
    return <View style={[styles.fallback, dimension, style]} />;
  }

  const uri = avatarId.startsWith('http') ? avatarId : `${SLEEPER_AVATAR_BASE}/${avatarId}`;

  return (
    <Image
      source={{ uri }}
      style={[dimension, style] as StyleProp<ImageStyle>}
      cachePolicy="disk"
      onError={() => setFailed(true)}
    />
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    fallback: {
      backgroundColor: colors.surfaceSolid,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: colors.border,
    },
  });
}
