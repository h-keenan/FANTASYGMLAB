import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, View, type ImageStyle, type StyleProp, type ViewStyle } from 'react-native';
import { Image } from 'expo-image';
import Animated, { Easing, useAnimatedStyle, useSharedValue, withRepeat, withTiming } from 'react-native-reanimated';

import { useThemeMode } from '../context/ThemeModeContext';
import type { ThemeColors } from '../theme';
import { resolvePlayerTier, tierGlowIntensity, type TierGlowIntensity } from '../lib/playerTier';

const SLEEPER_HEADSHOT_BASE = 'https://sleepercdn.com/content/nfl/players';

// coridian_, 2026-10-19 (queued cosmetic, lowest priority): "an effect
// around the prestige ring ... kind of a glowing effect, kind of a fire
// effect ... different for different tiers. Obviously lower tiers don't
// need one." RN has no cross-platform blurred box-shadow (iOS shadowRadius
// only, Android ignores it), so the "glow" is a soft halo View behind the
// avatar instead — a larger, low-opacity circle in the tier's own ring
// color that pulses opacity, same `withRepeat`/`withTiming` technique
// SkeletonBlock already uses. Bigger/brighter/faster for a higher tier.
const GLOW_STYLE_BY_INTENSITY: Record<Exclude<TierGlowIntensity, null>, { spread: number; peakOpacity: number; durationMs: number }> = {
  strong: { spread: 7, peakOpacity: 0.55, durationMs: 900 },
  medium: { spread: 5, peakOpacity: 0.4, durationMs: 1200 },
  subtle: { spread: 3, peakOpacity: 0.28, durationMs: 1500 },
};

function PrestigeGlow({ size, color, intensity }: { size: number; color: string; intensity: Exclude<TierGlowIntensity, null> }) {
  const { spread, peakOpacity, durationMs } = GLOW_STYLE_BY_INTENSITY[intensity];
  const pulse = useSharedValue(0);

  useEffect(() => {
    pulse.value = withRepeat(withTiming(1, { duration: durationMs, easing: Easing.inOut(Easing.ease) }), -1, true);
  }, [pulse, durationMs]);

  const animatedStyle = useAnimatedStyle(() => ({
    opacity: peakOpacity * (0.4 + pulse.value * 0.6),
  }));

  const haloSize = size + spread * 2;
  return (
    <Animated.View
      pointerEvents="none"
      style={[
        {
          position: 'absolute',
          width: haloSize,
          height: haloSize,
          borderRadius: haloSize / 2,
          backgroundColor: color,
          left: -spread,
          top: -spread,
        },
        animatedStyle,
      ]}
    />
  );
}

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
  // Same gate as the ring color: only a caller-supplied tier can glow,
  // never the plain untiered border.
  const glowIntensity = tier ? tierGlowIntensity(resolvePlayerTier(tier, isDark).tierId) : null;

  // Nothing will ever load for this avatar — settle immediately so a caller
  // waiting on onLoadSettle (e.g. a share-card capture gate) doesn't hang.
  useEffect(() => {
    if (!playerId) {
      onLoadSettle?.();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playerId]);

  if (!playerId || failed) {
    return (
      <View style={[{ width: size, height: size }, style]}>
        {glowIntensity ? <PrestigeGlow size={size} color={ringColor} intensity={glowIntensity} /> : null}
        <View style={[styles.fallback, dimension, ring]} />
      </View>
    );
  }

  return (
    <View style={[{ width: size, height: size }, style]}>
      {glowIntensity ? <PrestigeGlow size={size} color={ringColor} intensity={glowIntensity} /> : null}
      <Image
        source={{ uri: `${SLEEPER_HEADSHOT_BASE}/${playerId}.jpg` }}
        style={[dimension, ring] as StyleProp<ImageStyle>}
        cachePolicy="disk"
        // Checked ~45 real Sleeper headshots across positions/eras: every
        // source photo is landscape (roughly 300x200-350x254), so `cover`
        // against this square avatar box always crops left/right only — the
        // full photo height (and whatever headroom Sleeper framed above the
        // helmet) already shows with zero vertical slack to shift. `top`
        // is therefore a no-op on every image sampled today, same pixels as
        // the previous implicit `center` default; it's set explicitly (rather
        // than left to center) as a defensive default in case a future/rare
        // headshot ships portrait-oriented, where it would anchor the
        // face/helmet instead of letting a center crop clip it. `contentFit`
        // is made explicit too so this isn't relying on expo-image's default.
        contentFit="cover"
        contentPosition="top"
        onLoad={() => onLoadSettle?.()}
        onError={() => {
          setFailed(true);
          onLoadSettle?.();
        }}
      />
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    fallback: {
      backgroundColor: colors.surfaceSolid,
    },
  });
}
