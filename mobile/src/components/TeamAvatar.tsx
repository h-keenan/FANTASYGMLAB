import React, { useMemo, useState } from 'react';
import { StyleSheet, View, type ImageStyle, type StyleProp, type ViewStyle } from 'react-native';
import { Image } from 'expo-image';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import type { ThemeColors } from '../theme';

const SLEEPER_AVATAR_BASE = 'https://sleepercdn.com/avatars/thumbs';

interface TeamAvatarProps {
  avatarId: string | null | undefined;
  /** Name for the initials fallback when there is no (or a broken) avatar. */
  name?: string | null;
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
export default function TeamAvatar({ avatarId, name, size = 36, style }: TeamAvatarProps) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [failed, setFailed] = useState(false);
  const dimension = { width: size, height: size, borderRadius: size / 2 };

  if (!avatarId || failed) {
    const text = initialsOf(name);
    return (
      <View style={[styles.fallback, dimension, style, text ? styles.fallbackCentered : null]}>
        {text ? <AppText style={{ fontSize: size * 0.38, fontWeight: '800', color: colors.textSecondary }}>{text}</AppText> : null}
      </View>
    );
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

function initialsOf(name: string | null | undefined): string {
  const parts = (name ?? '').trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '';
  return (parts.length === 1 ? parts[0].slice(0, 2) : parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    fallbackCentered: { alignItems: 'center', justifyContent: 'center' },
    fallback: {
      backgroundColor: colors.surfaceSolid,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: colors.border,
    },
  });
}
