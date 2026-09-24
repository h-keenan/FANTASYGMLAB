import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import CircularProgressRing from './CircularProgressRing';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

/**
 * Rebuilt player identity block — photo left, name/position/team next to
 * it, and the "N OVR" ring anchored at the far right edge of the row
 * (opposite the photo) per coridian_'s explicit "option a" pick (Discord,
 * 2026-09-23) — the ring used to sit directly above the name, immediately
 * next to the photo. Classification tags, actions, roster recommendation,
 * and news alerts are NOT this component's job — PlayerDetailScreen
 * renders those below as `children` so this stays a single-purpose
 * identity header, reusable anywhere a compact player portrait+rating+name
 * is needed.
 */
export default function PlayerHero({
  playerId,
  tier,
  name,
  position,
  team,
  overallRating,
  ringColor,
  glowColor,
  children,
}: {
  playerId: string;
  tier?: string | null;
  name: string;
  position?: string | null;
  team?: string | null;
  /** 0-99 headline rating, null when the position pool is too thin to rank
   * against — the ring is simply omitted, never a fabricated value. */
  overallRating: number | null;
  ringColor: string;
  /** Subtle background tint behind the portrait — driven by the player's
   * own tier color (no team-color asset exists in this app yet), never a
   * fixed/generic color. */
  glowColor: string;
  children?: React.ReactNode;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.wrap}>
      <View style={styles.identityRow}>
        <View style={styles.avatarWrap}>
          <View style={[styles.glow, { backgroundColor: glowColor }]} />
          <PlayerAvatar playerId={playerId} size={100} tier={tier} style={styles.avatar} />
        </View>
        <View style={styles.infoCol}>
          <AppText style={styles.name} numberOfLines={2}>
            {name}
          </AppText>
          <View style={styles.metaRow}>
            <PositionBadge position={position} size="md" />
            {team ? <AppText style={styles.team}>{team}</AppText> : null}
          </View>
        </View>
        {overallRating !== null ? (
          <CircularProgressRing
            percent={overallRating}
            size={68}
            strokeWidth={6}
            valueLabel={String(overallRating)}
            valueFontScale={0.36}
            color={ringColor}
            label="OVR"
          />
        ) : null}
      </View>
      {children}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { marginBottom: spacing.lg },
    identityRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.lg },
    avatarWrap: { alignItems: 'center', justifyContent: 'center' },
    glow: {
      position: 'absolute',
      width: 132,
      height: 132,
      borderRadius: 66,
      opacity: 0.22,
    },
    avatar: {
      shadowColor: '#000',
      shadowOpacity: 0.3,
      shadowRadius: 10,
      shadowOffset: { width: 0, height: 4 },
    },
    infoCol: { flex: 1, alignItems: 'flex-start', gap: 4 },
    name: { fontSize: 24, fontWeight: '800', color: colors.textPrimary, lineHeight: 27 },
    metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
    team: { fontSize: 14, fontWeight: '600', color: colors.textSecondary },
  });
}
