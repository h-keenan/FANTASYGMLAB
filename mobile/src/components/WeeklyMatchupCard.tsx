import React, { useMemo } from 'react';
import { StyleSheet, View, type ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from './AnimatedCard';
import AppText from './AppText';
import TeamAvatar from './TeamAvatar';
import { useThemeMode } from '../context/ThemeModeContext';
import type { MatchupResponse } from '../lib/api';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * Compact weekly-matchup summary: who you're playing, each side's
 * season-value total, and the resulting edge. Promoted out of
 * DashboardScreen (Next Move) so League Overview can lead with the exact
 * same matchup read instead of a page-local duplicate (UI_HIERARCHY_DIRECTIVE
 * §9/§10: shared patterns get promoted, not re-implemented per screen).
 *
 * Shows the season-value edge, NOT a points projection: the app has no
 * weekly-projection feed (see services/mobile_api_service.py's
 * SEASON_VALUE_BASIS_LABEL), so the number here is a season-long
 * value/opportunity total and the card says so on its face.
 *
 * `glow` lets a caller mark this card as the screen's one dominant module
 * (AnimatedCard's own glow docstring: reserved for the one or two most
 * important cards on a screen) — Next Move keeps it un-glowed since its Hero
 * briefing card already owns that role there; League Overview passes `glow`
 * since coridian_'s 2026-10 brief puts the matchup at the very top of that
 * screen.
 */
export default function WeeklyMatchupCard({
  matchup,
  onPress,
  glow = false,
}: {
  matchup: MatchupResponse;
  onPress: () => void;
  glow?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const mine = matchup.my_team;
  const opponent = matchup.opponent;
  const comparison = matchup.comparison;
  if (!mine || !opponent || !comparison) return null;

  const edgeColor =
    comparison.edge === 'you'
      ? colors.successBright
      : comparison.edge === 'opponent'
        ? colors.danger
        : colors.textSecondary;

  return (
    <AnimatedCard
      glow={glow}
      style={StyleSheet.flatten([styles.card, { borderLeftColor: colors.accent } as ViewStyle])}
      onPress={onPress}
    >
      <View style={styles.cardHeaderRow}>
        <Ionicons name="american-football" size={15} color={colors.accent} style={styles.cardIcon} />
        <AppText style={[styles.cardLabel, { color: colors.accent }]}>
          {matchup.week != null ? `WEEK ${matchup.week} MATCHUP` : 'THIS WEEK’S MATCHUP'}
        </AppText>
      </View>
      <AppText style={styles.cardHeadline}>vs {opponent.team_name}</AppText>

      <View style={styles.matchupValueRow}>
        <View style={styles.matchupValueSide}>
          <TeamAvatar
            avatarId={mine.avatar_url}
            size={40}
            style={StyleSheet.flatten([styles.matchupAvatar, { borderColor: colors.accent }])}
          />
          <AppText style={styles.matchupSideLabel}>YOU</AppText>
          <AppText style={styles.matchupSideValue}>{Math.round(comparison.my_season_value).toLocaleString()}</AppText>
        </View>
        <AppText style={styles.matchupVersus}>VS</AppText>
        <View style={[styles.matchupValueSide, styles.matchupValueSideRight]}>
          <TeamAvatar
            avatarId={opponent.avatar_url}
            size={40}
            style={StyleSheet.flatten([styles.matchupAvatar, { borderColor: colors.danger }])}
          />
          <AppText style={styles.matchupSideLabel}>THEM</AppText>
          <AppText style={styles.matchupSideValue}>{Math.round(comparison.opponent_season_value).toLocaleString()}</AppText>
        </View>
      </View>

      <AppText style={[styles.matchupEdge, { color: edgeColor }]}>
        {comparison.headline}
        {comparison.edge === 'even'
          ? ''
          : ` (${comparison.margin > 0 ? '+' : ''}${Math.round(comparison.margin).toLocaleString()})`}
      </AppText>
      {/* Straight from the API, never paraphrased into something stronger. */}
      <AppText style={styles.matchupBasis}>{comparison.basis_label}</AppText>

      <View style={styles.destButton}>
        <AppText style={styles.destButtonText}>SEE SUGGESTED STARTERS</AppText>
      </View>
    </AnimatedCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: {
      borderLeftWidth: 4,
      padding: spacing.lg,
      marginBottom: spacing.sm,
    },
    cardHeaderRow: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.xs },
    cardIcon: { marginRight: spacing.xs },
    cardLabel: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.4 },
    cardHeadline: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: 4 },
    matchupValueRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginTop: spacing.md,
    },
    matchupValueSide: { flex: 1 },
    matchupValueSideRight: { alignItems: 'flex-end' },
    matchupAvatar: { borderWidth: 2, marginBottom: spacing.xs },
    matchupSideLabel: { fontSize: 10, fontWeight: '800', letterSpacing: 0.6, color: colors.textTertiary },
    matchupSideValue: { fontSize: 20, fontWeight: '800', color: colors.textPrimary, marginTop: 2 },
    matchupVersus: {
      fontSize: 11,
      fontWeight: '800',
      letterSpacing: 0.8,
      color: colors.textTertiary,
      paddingHorizontal: spacing.sm,
    },
    matchupEdge: { fontSize: 13, fontWeight: '700', marginTop: spacing.md },
    matchupBasis: { fontSize: 11, color: colors.textTertiary, lineHeight: 16, marginTop: spacing.xs },
    destButton: {
      marginTop: spacing.md,
      borderWidth: 1.5,
      borderColor: colors.accent,
      borderRadius: radii.sm,
      paddingVertical: spacing.sm,
      alignItems: 'center',
    },
    destButtonText: { fontSize: 12, fontWeight: '700', color: colors.accent, letterSpacing: 0.4 },
  });
}
