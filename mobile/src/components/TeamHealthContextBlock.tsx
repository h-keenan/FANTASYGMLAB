import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import CompactPlayerModule from './CompactPlayerModule';
import { useThemeMode } from '../context/ThemeModeContext';
import type { InjuryImpactPlayer, TeamSnapshot } from '../lib/api';
import { spacing, type ThemeColors } from '../theme';

/** True when a team snapshot has anything worth rendering as injury/health
 * context — the same gate both Next Move (Needs Attention) and League
 * Overview (Injury Concerns) use before showing this block at all. */
export function hasHealthContext(snapshot: TeamSnapshot | null): boolean {
  if (!snapshot) return false;
  const players = snapshot.top_injury_impact_players ?? [];
  const keyInjuries = snapshot.key_injuries_summary?.trim() ?? '';
  const fallbackSummary = snapshot.top_injury_impact_summary?.trim() ?? '';
  return players.length > 0 || Boolean(keyInjuries) || Boolean(fallbackSummary);
}

/** The "why" portion of an injury-impact card's context line — status,
 * roster relevance, impact contribution, and freshness caveat. Identity
 * (name/position/team/tier) is rendered by CompactPlayerModule itself, so
 * this only covers what that module can't show. Mirrors the engine's own
 * top_injury_impact_summary wording (status, impact N, freshness) that web
 * renders, trimmed for a phone-width row. */
function injuryImpactContextLine(player: InjuryImpactPlayer): string {
  const status = player.injury_status || player.injury_level;
  return [
    status,
    player.roster_relevance,
    player.impact_contribution != null ? `impact ${player.impact_contribution}` : '',
    // Only surface freshness when it undercuts the read — "current"/"recent"
    // updates need no caveat, the same way web only notes stale/unknown ones.
    ['stale', 'aging', 'update unknown'].includes(player.freshness_label) ? player.freshness_label : '',
  ]
    .filter(Boolean)
    .join(' · ');
}

/** The "why" behind an injury-driven health flag: which injuries, and which
 * players are actually carrying the impact. Same already-computed fields web
 * shows as its "Key injuries:" caption plus the injury impact note.
 *
 * Shared between Next Move's Needs Attention group (where it renders as a
 * leading block inside a larger grouped surface, `last` controlling whether
 * the divider shows) and League Overview's standalone Injury Concerns
 * section (where it's the only thing in its own card, `last=true`) — same
 * data, same presentation, promoted into one component per
 * UI_HIERARCHY_DIRECTIVE §9/§10/§23 rather than duplicated per screen.
 */
export default function TeamHealthContextBlock({
  snapshot,
  last,
  onPlayerPress,
}: {
  snapshot: TeamSnapshot;
  last: boolean;
  onPlayerPress?: (player: InjuryImpactPlayer) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const players = snapshot.top_injury_impact_players ?? [];
  const keyInjuries = snapshot.key_injuries_summary?.trim() ?? '';
  const fallbackSummary = snapshot.top_injury_impact_summary?.trim() ?? '';

  return (
    <View style={[styles.healthBlock, !last && styles.groupDivider]}>
      <View style={styles.cardHeaderRow}>
        <Ionicons name="pulse-outline" size={15} color={colors.danger} style={styles.cardIcon} />
        <AppText style={[styles.cardLabel, { color: colors.danger }]} numberOfLines={1}>
          {(snapshot.health_flag || 'Health context').toUpperCase()}
        </AppText>
      </View>
      {keyInjuries ? <AppText style={styles.healthSummary}>Key injuries: {keyInjuries}</AppText> : null}
      {players.length > 0 ? (
        <View style={styles.detailListGroup}>
          <AppText style={styles.detailListLabel}>Driving the flag</AppText>
          {players.map((player, index) => (
            <CompactPlayerModule
              key={`${player.player_id || player.name}-${index}`}
              playerId={player.player_id || null}
              name={player.name}
              position={player.position || null}
              team={player.team || null}
              tier={player.tier || null}
              value={player.player_value_score}
              valueLabel="VALUE"
              contextLine={injuryImpactContextLine(player)}
              style={styles.injuryPlayerRow}
              onPress={player.player_id && onPlayerPress ? () => onPlayerPress(player) : undefined}
            />
          ))}
        </View>
      ) : fallbackSummary ? (
        <AppText style={styles.detailListItem}>{fallbackSummary}</AppText>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    groupDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.hairline },
    healthBlock: { paddingVertical: spacing.md, gap: spacing.sm },
    cardHeaderRow: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.xs },
    cardIcon: { marginRight: spacing.xs },
    cardLabel: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.4 },
    healthSummary: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
    detailListGroup: { gap: spacing.sm },
    detailListLabel: {
      fontSize: 11,
      fontWeight: '700',
      color: colors.textTertiary,
      textTransform: 'uppercase',
      letterSpacing: 0.4,
      marginBottom: 2,
    },
    detailListItem: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
    injuryPlayerRow: { paddingVertical: spacing.xs },
  });
}
