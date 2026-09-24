import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, View, type ImageStyle, type StyleProp, type ViewStyle } from 'react-native';
import { Image } from 'expo-image';

import { useThemeMode } from '../context/ThemeModeContext';
import type { ThemeColors } from '../theme';
import { resolvePlayerTier } from '../lib/playerTier';

const SLEEPER_HEADSHOT_BASE = 'https://sleepercdn.com/content/nfl/players';

interface PlayerAvatarProps {
  playerId: string | null | undefined;
  size?: number;
  tier?: string | null;
  style?: StyleProp<ViewStyle>;
  /**
   * Fires once this avatar has "settled" — the headshot finished loading,
   * failed to load, or there was never an id to load in the first place.
   * `react-native-view-shot`'s own docs note that `captureRef` does NOT wait
   * for in-flight `Image` loads: a caller that needs a snapshot to include
   * remote photos must trigger the capture only after every avatar's load
   * has resolved. Screens that render this off-screen for a view-shot
   * capture (see TradeShareCard/RecapShareCard) use this to gate that
   * capture; normal in-app usage can ignore it.
   */
  onLoadSettle?: () => void;
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
export default function PlayerAvatar({ playerId, size = 40, tier, style, onLoadSettle }: PlayerAvatarProps) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [failed, setFailed] = useState(false);
  const dimension = { width: size, height: size, borderRadius: size / 2 };
  const ringColor = tier ? resolvePlayerTier(tier, isDark).color : colors.border;
  const ring = { borderWidth: tier ? 2 : StyleSheet.hairlineWidth, borderColor: ringColor };

  // Nothing will ever load for this avatar — settle immediately so a caller
  // waiting on onLoadSettle (e.g. a share-card capture gate) doesn't hang.
  useEffect(() => {
    if (!playerId) {
      onLoadSettle?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playerId]);

  if (!playerId || failed) {
    return <View style={[styles.fallback, dimension, ring, style]} />;
  }

  return (
    <Image
      source={{ uri: `${SLEEPER_HEADSHOT_BASE}/${playerId}.jpg` }}
      style={[dimension, ring, style] as StyleProp<ImageStyle>}
      cachePolicy="disk"
      onLoad={() => onLoadSettle?.()}
      onError={() => {
        setFailed(true);
        onLoadSettle?.();
      }}
    />
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    fallback: {
      backgroundColor: colors.surfaceSolid,
    },
  });
}
