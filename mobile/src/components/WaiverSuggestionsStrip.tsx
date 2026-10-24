import React, { useMemo } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';

import AnimatedCard from './AnimatedCard';
import AppText from './AppText';
import MeterRow, { confidenceLevelFor } from './ConfidenceMeter';
import FAABGuidance from './FAABGuidance';
import OverallRatingBadge from './OverallRatingBadge';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import SectionHeading from './SectionHeading';
import { bestAvailableCardVisual } from '../lib/bestAvailableCardVisual';
import { positionRankPrestige } from '../lib/positionRankPrestige';
import type { WaiverPriorityAdd } from '../lib/api';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

/**
 * "Waiver Suggestions": the top Priority Adds as a horizontal strip of small
 * square player cards (moved here from the retired League Overview screen so
 * Dashboard, the one landing, owns it). Same prestige-tier glow border /
 * OVR-top-right / name-bottom treatment as Waivers' Best Available cards,
 * reusing `positionRankPrestige` + `bestAvailableCardVisual` unmodified.
 * `WaiverPriorityAdd` extends `WaiverPlayer`, so the position_rank is the same
 * wire-relative free-agent-pool rank Best Available feeds through that tier
 * decision. OVR uses `overall_rating` (0-99), never the wire-relative `score`.
 * Capped at 3 so the strip does not scroll on a normal phone width.
 */
export default function WaiverSuggestionsStrip({
  adds,
  onPressPlayer,
}: {
  adds: WaiverPriorityAdd[];
  onPressPlayer: (player: WaiverPriorityAdd) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (adds.length === 0) return null;
  return (
    <View>
      <SectionHeading title="Waiver Suggestions" icon="swap-horizontal-outline" />
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.suggestionRow}>
        {adds.slice(0, 3).map((player) => (
          <WaiverSuggestionCard key={player.player_id} player={player} onPress={() => onPressPlayer(player)} />
        ))}
      </ScrollView>
    </View>
  );
}

function WaiverSuggestionCard({ player, onPress }: { player: WaiverPriorityAdd; onPress: () => void }) {
  const { colors, isDark } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const prestige = positionRankPrestige(player.position_rank, isDark);
  const visual = bestAvailableCardVisual(prestige.tier);
  return (
    <AnimatedCard
      style={styles.suggestionCard}
      onPress={onPress}
      glow={visual.glow}
      glowColor={prestige.color ?? undefined}
    >
      <View style={styles.suggestionTopRow}>
        {visual.prestigeLabel ? (
          <AppText style={[styles.suggestionPrestigeLabel, { color: prestige.color ?? colors.textTertiary }]}>
            {visual.prestigeLabel}
          </AppText>
        ) : (
          <View />
        )}
        <OverallRatingBadge rating={player.overall_rating} positionRank={player.position_rank} />
      </View>
      <PlayerAvatar playerId={player.player_id} size={40} tier={player.tier} style={styles.suggestionAvatar} />
      <View style={styles.suggestionPosBadgeWrap}>
        <PositionBadge position={player.position} size="sm" />
      </View>
      <AppText style={styles.suggestionName} numberOfLines={1}>
        {player.name ?? 'Unknown'}
      </AppText>
      <View style={styles.suggestionFooter}>
        <FAABGuidance faab={player.faab} size="compact" />
        {player.confidence_label ? (
          <MeterRow
            label="CONFIDENCE"
            value={player.confidence_label}
            level={confidenceLevelFor(player.confidence_label)}
            color={colors.premium}
          />
        ) : null}
      </View>
    </AnimatedCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    suggestionRow: { flexDirection: 'row', gap: spacing.sm, paddingRight: spacing.lg },
    suggestionCard: { width: 184, padding: spacing.sm, alignItems: 'center', gap: 2 },
    suggestionTopRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      alignSelf: 'stretch',
      minHeight: 14,
      marginBottom: spacing.xs,
    },
    suggestionPrestigeLabel: { fontSize: 10, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.5 },
    suggestionAvatar: { marginTop: 2 },
    suggestionPosBadgeWrap: { alignSelf: 'center', marginTop: spacing.xs },
    suggestionName: { fontSize: 15, fontWeight: '800', color: colors.textPrimary, marginTop: spacing.xs },
    suggestionFooter: { alignSelf: 'stretch', alignItems: 'center', gap: 4, marginTop: spacing.xs },
  });
}
